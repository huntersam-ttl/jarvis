"""Coding Agent — LLM reasoning loop over deterministic tools.

The LLM never executes anything itself. Each step it proposes ONE tool
call as strict JSON; the agent executes it with CodingTools and records
the outcome. The loop ends when the model signals done, a step fails
fatally, the step budget is exhausted, or the task is cancelled.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.agents.base import Agent, AgentError
from app.agents.coding.schemas import ActionRecord, CodingTask
from app.agents.coding.tools import (
    ApprovalRequired,
    CodingTools,
    ToolContext,
    ToolError,
    TOOL_NAMES,
)
from app.core.logging import get_logger
from app.providers.base import Provider

logger = get_logger("jarvis.agents.coding")

SYSTEM_PROMPT = """You are Jarvis's Coding Agent. You work inside ONE approved \
project directory and solve a coding task step by step.

At every turn reply with ONLY a JSON object, no markdown fences, in this shape:

{"thought": "<one sentence reasoning>", "tool": "<tool name>", "args": {...}}

or, when the task is finished (or impossible):

{"thought": "<one sentence>", "done": true, "summary": "<what was done / result>"}

Available tools:
- list_files {"path": "."}
- read_file {"path": "relative/path.py"}
- write_file {"path": "...", "content": "full new file content"}
- replace_text {"path": "...", "old_text": "...", "new_text": "..."}
- run_command {"command": "...", "timeout": 120}
- git_status {}, git_diff {}, git_log {"limit": 10}
- git_add {"paths": "-A"}, git_commit {"message": "..."}
- run_tests {} or {"command": "pytest -q tests/test_x.py"}
- run_build {} or {"command": "npm run build"}

Rules:
- Paths are relative to the project root. Never touch files outside it.
- Never read or modify .env or secret files.
- Prefer replace_text over rewriting whole files.
- Run tests/build to verify your work before declaring done.
- If a tool errors, adapt; do not repeat the same failing call more than twice.
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_llm_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise AgentError("Model did not return JSON")
    return json.loads(match.group(0))


class CodingAgent(Agent):
    name = "coding"

    def __init__(self, provider: Provider):
        self._provider = provider
        self._task: Optional[CodingTask] = None
        self._cancel_requested = False
        self._lock: Optional[asyncio.Lock] = None

    # ---- Agent interface ---------------------------------------------
    async def health_check(self) -> bool:
        return self._task is None or self._task.status == "working"

    async def status(self) -> dict:
        return {
            "agent": self.name,
            "status": "working" if self._task and self._task.status == "working" else "ready",
            "has_active_task": bool(self._task and self._task.status == "working"),
            "task": self._task,
        }

    async def run(self, instruction: str, project_path: Optional[str] = None) -> str:
        """Blocking run used internally; the service wraps this in a task."""
        raise NotImplementedError("Use service.submit()")

    # ---- public task API ------------------------------------------------
    async def submit(
        self,
        instruction: str,
        project_path: str,
        max_steps: int = 12,
        approve_destructive: bool = False,
        model: Optional[str] = None,
    ) -> CodingTask:
        async with (self._lock or asyncio.Lock()):
            if self._task and self._task.status == "working":
                raise AgentError("A coding task is already running")
            self._cancel_requested = False
            self._task = CodingTask(
                id=uuid.uuid4().hex[:12],
                status="working",
                current_task=instruction,
                project_path=project_path,
                started_at=_utcnow(),
            )
        asyncio.create_task(
            self._execute(instruction, project_path, max_steps, approve_destructive, model)
        )
        return self._task

    async def cancel(self) -> CodingTask:
        self._cancel_requested = True
        if self._task and self._task.status == "working":
            self._task.status = "cancelled"
            self._task.finished_at = _utcnow()
            self._task.last_error = "Cancelled by user"
        return self._task

    @property
    def task(self) -> Optional[CodingTask]:
        return self._task

    # ---- execution loop ---------------------------------------------------
    async def _execute(
        self,
        instruction: str,
        project_path: str,
        max_steps: int,
        approve_destructive: bool,
        model: Optional[str],
    ) -> None:
        task = self._task
        assert task is not None
        ctx = ToolContext(project_root=project_path, allow_destructive=approve_destructive)
        tools = CodingTools(ctx)
        tool_results: list[str] = []

        try:
            for step in range(1, max_steps + 1):
                if self._cancel_requested:
                    task.last_error = "Cancelled by user"
                    return
                task.steps_taken = step

                prompt = self._build_prompt(instruction, project_path, tool_results)
                started = time.perf_counter()
                reply, _used = await self._provider.chat(prompt, model=model)
                decision = _parse_llm_json(reply)

                if decision.get("done"):
                    task.status = "completed"
                    task.result = str(decision.get("summary", "Done"))[:1000]
                    return

                tool = str(decision.get("tool", "")).strip()
                args = decision.get("args") or {}
                if tool not in TOOL_NAMES:
                    tool_results.append(f"step {step}: unknown tool '{tool}'")
                    task.actions.append(self._record(step, tool, "", False,
                        detail=f"Unknown tool '{tool}'", started=started))
                    continue

                record = self._execute_tool(step, tool, args, tools, started)
                task.actions.append(record)
                tool_results.append(
                    f"step {step} {tool}({record.args_summary[:80]}) -> "
                    f"{'OK' if record.ok else 'FAILED'}: "
                    f"{record.detail or record.output_preview[:300]}"
                )
                if record.approval_required:
                    task.last_error = record.detail
                    task.status = "failed"
                    task.finished_at = _utcnow()
                    return

            task.status = "failed"
            task.last_error = f"Step budget exhausted ({max_steps} steps)"
        except AgentError as exc:
            task.status = "failed"
            task.last_error = str(exc)
        except Exception as exc:  # defensive: never crash the runner
            logger.exception("coding agent task failed")
            task.status = "failed"
            task.last_error = str(exc)[:500]
        finally:
            if task.status == "working":
                task.status = "failed"
                task.last_error = task.last_error or "Task ended unexpectedly"
            task.finished_at = task.finished_at or _utcnow()

    # ---- helpers -----------------------------------------------------------
    def _build_prompt(self, instruction: str, project_path: str, tool_results: list[str]) -> str:
        history = "\n".join(tool_results[-8:])
        return (
            f"Project root: {project_path}\n"
            f"Task: {instruction}\n\n"
            f"Previous tool results (most recent last):\n"
            f"{history or '(none yet — start by listing files)'}\n\n"
            "Reply with the next JSON decision now."
        )

    def _execute_tool(
        self, step: int, tool: str, args: dict, tools: CodingTools, started: float
    ) -> ActionRecord:
        args_summary = ", ".join(f"{k}={str(v)[:40]}" for k, v in args.items())[:200]
        record = ActionRecord(
            id=uuid.uuid4().hex[:8], step=step, tool=tool, args_summary=args_summary,
            ok=False, started_at=_utcnow(),
        )
        try:
            output, ok = self._dispatch(tool, args, tools)
            record.ok = ok
            record.detail = output.splitlines()[0][:200] if output else "OK"
            record.output_preview = output[:2000]
        except ApprovalRequired as exc:
            record.approval_required = True
            record.detail = str(exc)
        except ToolError as exc:
            record.detail = str(exc)
        except Exception as exc:  # defensive
            record.detail = f"Tool crashed: {exc}"
        record.duration_ms = round((time.perf_counter() - started) * 1000, 1)
        return record

    def _dispatch(self, tool: str, args: dict, tools: CodingTools):
        if tool == "list_files":
            return tools.list_files(str(args.get("path", "."))), True
        if tool == "read_file":
            return tools.read_file(str(args.get("path", ""))), True
        if tool == "write_file":
            return tools.write_file(str(args.get("path", "")), str(args.get("content", ""))), True
        if tool == "replace_text":
            return tools.replace_text(
                str(args.get("path", "")),
                str(args.get("old_text", "")),
                str(args.get("new_text", "")),
            ), True
        if tool == "run_command":
            return tools.run_command(str(args.get("command", "")), int(args.get("timeout", 120)))
        if tool == "git_status":
            return tools.git_status(), True
        if tool == "git_diff":
            return tools.git_diff(bool(args.get("staged", False))), True
        if tool == "git_log":
            return tools.git_log(int(args.get("limit", 10))), True
        if tool == "git_add":
            return tools.git_add(str(args.get("paths", "-A"))), True
        if tool == "git_commit":
            return tools.git_commit(str(args.get("message", "Jarvis coding agent commit"))), True
        if tool == "run_tests":
            return tools.run_tests(args.get("command"))
        if tool == "run_build":
            return tools.run_build(args.get("command"))
        raise ToolError(f"Unknown tool: {tool}")

    def _record(self, step, tool, args_summary, ok, detail="", started=None) -> ActionRecord:
        return ActionRecord(
            id=uuid.uuid4().hex[:8], step=step, tool=tool,
            args_summary=args_summary, ok=ok, detail=detail,
            started_at=_utcnow(),
            duration_ms=round((time.perf_counter() - started) * 1000, 1) if started else 0.0,
        )

