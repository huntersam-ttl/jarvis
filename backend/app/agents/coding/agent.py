"""Engineering Agent — LLM reasoning loop over deterministic tools.

Extends the original Coding Agent with a disciplined lifecycle:
QUEUED → ANALYZING → PLANNING → IMPLEMENTING → TESTING → (DEBUGGING) →
REVIEWING → VERIFYING → COMPLETED. Completion for code-changing tasks is
gated by deterministic verification (verifier.py), never by the model's
own claim of being done. Deterministic tools remain the only executors.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from app.agents.base import Agent, AgentError
from app.agents.coding.context import ContextBuilder
from app.agents.coding.planner import Plan, generate_plan
from app.agents.coding.project_analyzer import ProjectProfile, analyze_project
from app.agents.coding.reviewer import review_diff
from app.agents.coding.schemas import (
    ActionRecord,
    CodingTask,
    ReviewResultModel,
    TaskPlan,
    VerificationResultModel,
)
from app.agents.coding.tools import (
    ApprovalRequired,
    CodingTools,
    ToolContext,
    ToolError,
    TOOL_NAMES,
)
from app.agents.coding.verifier import run_verification
from app.core.logging import get_logger
from app.providers.base import Provider
from app.skills.registry import SkillRegistry

logger = get_logger("jarvis.agents.coding")

TOOL_PROMPT = """You are Jarvis's Engineering Agent working inside ONE approved \
project directory. Follow the provided engineering skills and plan.

At every turn reply with ONLY a JSON object, no markdown fences:

{"thought": "<one sentence>", "tool": "<tool name>", "args": {...}}
or when your implementation work is finished for now:
{"thought": "<one sentence>", "done": true, "summary": "<what changed>"}

Available tools:
- list_files {"path": "."} / search_files {"pattern": "..."}
- read_file {"path": "..."} / read_file_lines {"path": "...", "start": 1, "end": 40}
- write_file {"path": "...", "content": "..."} / replace_text {"path": "...", "old_text": "...", "new_text": "..."}
- create_directory {"path": "..."} / move_path {"src": "...", "dst": "..."}
- run_command {"command": "...", "timeout": 120}
- git_status {}, git_diff {}, git_log {"limit": 10}, git_add {"paths": "-A"}, git_commit {"message": "..."}
- git_branch {"name": "..."} / git_checkout {"name": "...", "create": true}
- run_tests {} / run_build {}

Rules:
- Relative paths only; never touch files outside the project or secrets.
- Follow the plan steps in order; smallest correct edits; run the provided tests.
- If a tool fails, diagnose the root cause; never repeat the same failing call more than twice.
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

    def __init__(
        self,
        provider: Provider,
        skill_registry: Optional[SkillRegistry] = None,
        on_update: Optional[Callable[[CodingTask], None]] = None,
    ):
        self._provider = provider
        self._registry = skill_registry or SkillRegistry()
        self._on_update = on_update
        self._task: Optional[CodingTask] = None
        self._cancel_requested = False
        self._lock: Optional[asyncio.Lock] = None
        self._profiles: dict = {}  # project_path -> ProjectProfile cache

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
        max_repair_loops: int = 2,
        max_reviewer_calls: int = 1,
        max_cost_usd: Optional[float] = None,
        auto_commit: bool = True,
    ) -> CodingTask:
        async with (self._lock or asyncio.Lock()):
            if self._task and self._task.status == "working":
                raise AgentError("A coding task is already running")
            self._cancel_requested = False
            self._task = CodingTask(
                id=uuid.uuid4().hex[:12],
                status="working",
                phase="QUEUED",
                checkpoint="TASK_CREATED",
                current_task=instruction,
                project_path=project_path,
                started_at=_utcnow(),
            )
        if self._on_update:
            try:
                self._on_update(self._task)
            except Exception:
                logger.exception("task persistence failed")
        asyncio.create_task(
            self._execute(
                instruction, project_path, max_steps, approve_destructive, model,
                max_repair_loops=max_repair_loops,
                max_reviewer_calls=max_reviewer_calls,
                max_cost_usd=max_cost_usd,
                auto_commit=auto_commit,
            )
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

    # ---- durable recovery --------------------------------------------------
    @staticmethod
    def _git_snapshot(project_path: str) -> tuple:
        """Deterministic (branch, changed_files) snapshot. No LLM involved."""
        import subprocess

        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=project_path, capture_output=True, text=True, timeout=10,
            )
            branch = proc.stdout.strip() if proc.returncode == 0 else None
            proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_path, capture_output=True, text=True, timeout=10,
            )
            files = sorted(
                line[3:].strip() for line in proc.stdout.splitlines() if len(line) > 3
            ) if proc.returncode == 0 else []
            return branch, files
        except (OSError, subprocess.TimeoutExpired):
            return None, None

    def _fail_recovery(self, task: CodingTask, reason: str) -> CodingTask:
        task.status = "failed"
        task.phase = "FAILED"
        task.finished_at = _utcnow()
        task.last_error = f"Recovery aborted (safety): {reason}"
        if self._on_update:
            try:
                self._on_update(task)
            except Exception:
                logger.exception("task persistence failed")
        return task

    async def recover(self, task: CodingTask) -> CodingTask:
        """Deterministic recovery of an interrupted task from its checkpoint.

        Never repeats destructive/deployment work, never re-runs a completed
        commit, and never resumes mid-LLM-generation (checkpoints are only
        written between stages).
        """
        if self._task and self._task.status == "working":
            task.status = "failed"
            task.last_error = "Recovery skipped: another task is active"
            return task

        task.status = "working"
        task.phase = "RECOVERING"
        self._cancel_requested = False
        self._task = task
        if self._on_update:
            try:
                self._on_update(task)
            except Exception:
                logger.exception("task persistence failed")

        checkpoint = task.checkpoint
        file_change_checkpoints = {
            "FILES_CHANGED", "VERIFICATION_COMPLETE", "REVIEW_COMPLETE",
        }

        # ---- git safety ------------------------------------------------
        profile = self.profile_for(task.project_path)
        if profile.has_git:
            branch, files = self._git_snapshot(task.project_path)
            if files is None:
                return self._fail_recovery(task, "git repository unreadable")
            if checkpoint in file_change_checkpoints:
                if task.git_branch and branch != task.git_branch:
                    return self._fail_recovery(
                        task,
                        f"branch changed since checkpoint "
                        f"(expected {task.git_branch!r}, found {branch!r})",
                    )
                if sorted(task.changed_files or []) != files:
                    return self._fail_recovery(
                        task,
                        "changed files differ from checkpoint state "
                        f"(checkpoint={task.changed_files}, current={files})",
                    )
            else:
                if files:
                    return self._fail_recovery(
                        task,
                        f"repository unexpectedly dirty for checkpoint "
                        f"{checkpoint}: {files}",
                    )
        elif checkpoint in file_change_checkpoints:
            return self._fail_recovery(
                task, "files changed but project has no git repository to verify against"
            )

        # ---- deterministic dispatch (no LLM calls for decisions) ---------
        await self._execute(
            task.current_task,
            task.project_path,
            max_steps=12,
            approve_destructive=False,
            model=None,
            resume_checkpoint=checkpoint,
        )
        return self._task

    def profile_for(self, project_path: str) -> ProjectProfile:
        cached = self._profiles.get(project_path)
        if cached is None:
            cached = analyze_project(project_path)
            self._profiles[project_path] = cached
        return cached

    # ---- model call wrapper with cost tracking -----------------------------
    async def _model_call(self, prompt: str, model: Optional[str]) -> str:
        task = self._task
        assert task is not None
        task.model_calls += 1
        reply, _used = await self._provider.chat(prompt, model=model)
        usage = getattr(self._provider, "last_usage", None)
        if isinstance(usage, dict):
            task.estimated_tokens += int(usage.get("total_tokens") or 0)
            cost = usage.get("total_cost") or usage.get("cost")
            if cost is not None:
                task.estimated_cost_usd += float(cost)
        else:
            task.estimated_tokens += ContextBuilder.estimate_tokens(prompt) * 2
        return reply


    # ---- execution loop ---------------------------------------------------
    async def _execute(
        self,
        instruction: str,
        project_path: str,
        max_steps: int,
        approve_destructive: bool,
        model: Optional[str],
        max_repair_loops: int = 2,
        max_reviewer_calls: int = 1,
        max_cost_usd: Optional[float] = None,
        auto_commit: bool = True,
        resume_checkpoint: str = "",
    ) -> None:
        task = self._task
        assert task is not None
        ctx = ToolContext(project_root=project_path, allow_destructive=approve_destructive)
        tools = CodingTools(ctx)

        def persist() -> None:
            if self._on_update:
                try:
                    self._on_update(task)
                except Exception:  # defensive: persistence must not kill tasks
                    logger.exception("task persistence failed")

        try:
            # ---- ANALYZING (skipped when resuming past analysis) -------------
            if resume_checkpoint in ("", "TASK_CREATED"):
                task.phase = "ANALYZING"
                persist()
                profile = self.profile_for(project_path)
                task.checkpoint = "ANALYSIS_COMPLETE"
                persist()
            else:
                profile = self.profile_for(project_path)

            # ---- PLANNING (re-run only when the checkpoint predates it) ------
            if resume_checkpoint in ("", "TASK_CREATED", "ANALYSIS_COMPLETE"):
                task.phase = "PLANNING"
                skills = self._registry.select(instruction)
                task.skills_used = [s.name for s in skills]
                persist()
                plan: Plan = await generate_plan(
                    self._provider, instruction,
                    ContextBuilder(profile, skills).profile_summary(), model=model,
                )
                task.plan = TaskPlan(
                    objective=plan.objective,
                    complexity=plan.complexity,
                    assumptions=plan.assumptions,
                    files=plan.files,
                    steps=[{"title": s.title, "verify": s.verify} for s in plan.steps],
                    risks=plan.risks,
                    verification=plan.verification,
                    rollback=plan.rollback,
                )
                task.checkpoint = "PLAN_COMPLETE"
                persist()
            else:
                skills = [
                    s for s in (
                        self._registry.get(name) for name in task.skills_used
                    ) if s
                ]

            context = ContextBuilder(profile, skills)
            plan_objective = task.plan.objective if task.plan else ""

            # ---- mode selection (deterministic, from checkpoint) --------------
            if resume_checkpoint == "FILES_CHANGED":
                mode = "verify"           # inspect diff, resume VERIFYING
            elif resume_checkpoint in ("VERIFICATION_COMPLETE", "REVIEW_COMPLETE"):
                mode = "review"           # resume REVIEWING / finalize
            else:
                mode = "full"

            await self._finish_task(
                task, tools, context, profile, instruction, plan_objective, model,
                max_steps, max_repair_loops, max_reviewer_calls, max_cost_usd,
                auto_commit, mode,
                review_done=(resume_checkpoint == "REVIEW_COMPLETE"),
            )
            return
        except AgentError as exc:
            task.status = "failed"
            task.phase = "FAILED"
            task.last_error = str(exc)
        except Exception as exc:  # defensive: never crash the runner
            logger.exception("engineering agent task failed")
            task.status = "failed"
            task.phase = "FAILED"
            task.last_error = str(exc)[:500]
        finally:
            if task.status == "working":
                task.status = "failed"
                task.phase = "FAILED"
                task.last_error = task.last_error or "Task ended unexpectedly"
            task.finished_at = task.finished_at or _utcnow()
            persist()

    # ---- verification gate → review → commit → complete ----------------------
    async def _finish_task(
        self,
        task: CodingTask,
        tools: CodingTools,
        context: ContextBuilder,
        profile: ProjectProfile,
        instruction: str,
        plan_objective: str,
        model: Optional[str],
        max_steps: int,
        max_repair_loops: int,
        max_reviewer_calls: int,
        max_cost_usd: Optional[float],
        auto_commit: bool,
        mode: str,  # full | verify | review
        review_done: bool = False,
    ) -> None:
        def persist() -> None:
            if self._on_update:
                try:
                    self._on_update(task)
                except Exception:
                    logger.exception("task persistence failed")

        failures = ""
        done_summary: Optional[str] = None
        first = True

        # ---- IMPLEMENTING → VERIFYING → DEBUGGING --------------------------
        while mode != "review":
            needs_impl = mode == "full" or not first or bool(failures)
            if needs_impl:
                task.phase = "IMPLEMENTING"
                persist()
                done_summary = await self._implementation_loop(
                    task, tools, context, instruction, failures, max_steps, model,
                    max_cost_usd=max_cost_usd,
                )
                if self._cancel_requested:
                    task.last_error = "Cancelled by user"
                    return
                if task.status != "working":
                    # approval_required / failure already recorded in the loop
                    task.finished_at = task.finished_at or _utcnow()
                    persist()
                    return
                # snapshot + checkpoint right after files changed
                branch, files = self._git_snapshot(str(task.project_path))
                task.git_branch = branch
                task.changed_files = files
                task.checkpoint = "FILES_CHANGED"
                persist()

            # ---- deterministic verification gate -----------------------------
            task.phase = "VERIFYING"
            persist()
            verification = run_verification(profile)
            task.verification = VerificationResultModel(
                passed=verification.passed,
                summary=verification.summary,
                checks=[c.__dict__ for c in verification.checks],
            )
            if verification.passed:
                task.checkpoint = "VERIFICATION_COMPLETE"
            persist()
            if verification.passed:
                break

            if task.repair_loops >= max_repair_loops:
                task.status = "failed"
                task.phase = "FAILED"
                task.last_error = (
                    f"COMPLETION DENIED — verification failed after "
                    f"{task.repair_loops} repair loops: {verification.summary}"
                )
                return
            task.repair_loops += 1
            task.phase = "DEBUGGING"
            failures = verification.failure_digest()
            persist()
            first = False

        # ---- REVIEWING (fresh-context model call) ------------------------------
        if review_done:
            # Finalize only if the existing completion rules still pass.
            if not (task.verification and task.verification.passed):
                task.status = "failed"
                task.phase = "FAILED"
                task.last_error = (
                    "Recovery aborted (safety): persisted verification does not pass"
                )
                return
            if task.review and task.review.verdict == "block":
                task.status = "failed"
                task.phase = "FAILED"
                task.last_error = (
                    "Recovery aborted (safety): persisted review blocked completion"
                )
                return
        elif max_reviewer_calls > 0 and profile.has_git:
            task.phase = "REVIEWING"
            persist()
            diff = tools.git_diff()
            review = await review_diff(self._provider, diff, instruction, model=model)
            task.model_calls += 1
            task.review = ReviewResultModel(
                verdict=review.verdict, summary=review.summary,
                findings=[f.__dict__ for f in review.findings],
            )
            if review.verdict != "block":
                task.checkpoint = "REVIEW_COMPLETE"
            persist()
            if review.verdict == "block":
                task.status = "failed"
                task.phase = "FAILED"
                blocking = "; ".join(
                    f"{f.severity}: {f.file}: {f.issue}" for f in review.blocking[:5]
                )
                task.last_error = f"Review blocked completion: {blocking}"
                return

        # ---- atomic commit (deterministic, no LLM) ------------------------------
        if auto_commit and profile.has_git and tools.git_diff() != "(no changes)":
            message = (
                f"jarvis: {plan_objective[:120]}" if plan_objective
                else "jarvis: engineering task"
            )
            tools.git_add("-A")
            commit_out = tools.git_commit(message)
            match = re.search(r"[0-9a-f]{7,40}", commit_out or "")
            task.git_commit = match.group(0) if match else None

        task.status = "completed"
        task.phase = "COMPLETED"
        task.checkpoint = "COMPLETED"
        task.result = done_summary or "Task completed and verified"

    # ---- implementation steps -----------------------------------------------
    async def _implementation_loop(
        self,
        task: CodingTask,
        tools: CodingTools,
        context: ContextBuilder,
        instruction: str,
        failures: str,
        max_steps: int,
        model: Optional[str],
        max_cost_usd: Optional[float] = None,
    ) -> Optional[str]:
        """Run model-driven tool steps until done / budget / failure."""
        tool_results: List[str] = []
        done_summary: Optional[str] = None
        malformed = 0

        for step in range(1, max_steps + 1):
            if self._cancel_requested:
                return None
            if max_cost_usd is not None and task.estimated_cost_usd >= max_cost_usd:
                raise AgentError(
                    f"Cost budget exhausted (${task.estimated_cost_usd:.2f} >= ${max_cost_usd:.2f})"
                )
            task.steps_taken = step
            task.phase = "IMPLEMENTING"

            prompt = TOOL_PROMPT + "\n\n" + context.build(
                instruction, tool_results, failures=failures
            )
            started = time.perf_counter()
            try:
                reply = await self._model_call(prompt, model)
            except AgentError:
                raise
            except Exception as exc:
                raise AgentError(f"Model call failed: {str(exc)[:200]}") from exc

            try:
                decision = _parse_llm_json(reply)
                malformed = 0
            except (AgentError, json.JSONDecodeError):
                malformed += 1
                if malformed >= 3:
                    raise AgentError("Model repeatedly returned malformed JSON")
                tool_results.append(f"step {step}: malformed model output, retrying")
                task.actions.append(self._record(step, "model", "", False,
                    detail="Malformed JSON from model — retrying", started=started))
                continue

            if decision.get("done"):
                done_summary = str(decision.get("summary", ""))[:1000]
                break

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
                task.phase = "WAITING_APPROVAL"
                return None

        if done_summary is None:
            task.last_error = f"Implementation budget exhausted ({max_steps} steps)"
            raise AgentError(task.last_error)
        return done_summary

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
        if tool == "search_files":
            return tools.search_files(str(args.get("pattern", "")), str(args.get("glob", "*"))), True
        if tool == "read_file_lines":
            return tools.read_file_lines(
                str(args.get("path", "")), int(args.get("start", 1)), int(args.get("end", 40))
            ), True
        if tool == "create_directory":
            return tools.create_directory(str(args.get("path", ""))), True
        if tool == "move_path":
            return tools.move_path(str(args.get("src", "")), str(args.get("dst", ""))), True
        if tool == "git_branch":
            return tools.git_branch(str(args.get("name", "")), bool(args.get("create", True))), True
        if tool == "git_checkout":
            return tools.git_checkout(str(args.get("name", "")), bool(args.get("create", False))), True
        raise ToolError(f"Unknown tool: {tool}")

    def _record(self, step, tool, args_summary, ok, detail="", started=None) -> ActionRecord:
        return ActionRecord(
            id=uuid.uuid4().hex[:8], step=step, tool=tool,
            args_summary=args_summary, ok=ok, detail=detail,
            started_at=_utcnow(),
            duration_ms=round((time.perf_counter() - started) * 1000, 1) if started else 0.0,
        )

