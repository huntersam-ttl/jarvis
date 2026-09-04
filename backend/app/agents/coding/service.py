"""Coding Agent service — task orchestration + simple project registry.

V1: one active coding task at a time, registry driven by the
JARVIS_ALLOWED_PROJECTS env setting (comma-separated absolute paths).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from app.agents.base import AgentError
from app.agents.coding.agent import CodingAgent
from app.agents.coding.schemas import CodingTask
from app.core.logging import get_logger

logger = get_logger("jarvis.agents.coding.service")


def build_allowed_projects(raw: str, jarvis_root: str) -> List[str]:
    """Parse the configured registry; always include the Jarvis project itself."""
    projects = {str(jarvis_root)}
    for p in (raw or "").split(","):
        p = p.strip()
        if p:
            projects.add(str(p))
    return sorted(projects)


class CodingAgentService:
    def __init__(self, agent, allowed_projects: List[str], store=None):
        self._agent = agent
        self._allowed_projects = allowed_projects
        self._store = store  # optional TaskStore (SQLite)

    # ---- registry -----------------------------------------------------
    @property
    def allowed_projects(self) -> List[str]:
        return self._allowed_projects

    def validate_project(self, project_path: str) -> str:
        resolved = str(Path(project_path).expanduser().resolve())
        if resolved not in self._allowed_projects:
            raise AgentError(
                "Project path is not in the allowed registry. "
                f"Allowed: {', '.join(self._allowed_projects)}"
            )
        return resolved

    def profile(self, project_path: str) -> dict:
        approved = self.validate_project(project_path)
        return self._agent.profile_for(approved).to_dict()

    def history(self, limit: int = 20) -> List[dict]:
        """Recent persisted tasks (survives restarts when a store is wired)."""
        if self._store is None:
            tasks = [self._agent.task.__dict__] if self._agent.task else []
        else:
            tasks = self._store.load_all()
        return tasks[:limit]

    # ---- task lifecycle --------------------------------------------------
    async def status(self) -> dict:
        return await self._agent.status()

    async def submit(
        self,
        instruction: str,
        project_path: str,
        model=None,
        max_steps: int = 12,
        approve_destructive: bool = False,
        max_repair_loops: int = 2,
        max_reviewer_calls: int = 1,
        max_cost_usd=None,
        auto_commit: bool = True,
    ) -> CodingTask:
        approved = self.validate_project(project_path)
        return await self._agent.submit(
            instruction=instruction,
            project_path=approved,
            max_steps=max_steps,
            approve_destructive=approve_destructive,
            model=model,
            max_repair_loops=max_repair_loops,
            max_reviewer_calls=max_reviewer_calls,
            max_cost_usd=max_cost_usd,
            auto_commit=auto_commit,
        )

    async def task(self, task_id: str) -> CodingTask:
        task = self._agent.task
        if task is None or task.id != task_id:
            raise AgentError(f"Unknown coding task: {task_id}")
        return task

    async def cancel(self, task_id: str) -> CodingTask:
        await self.task(task_id)  # raises if unknown
        return await self._agent.cancel()

    # ---- restart recovery ------------------------------------------------
    async def recover_interrupted(self) -> List[dict]:
        """Recover non-terminal persisted tasks after a backend restart.

        Deterministic: reads checkpoints from SQLite, validates git state,
        and resumes from the checkpoint. Terminal tasks are never resumed.
        """
        if self._store is None:
            return []
        results: List[dict] = []
        for payload in self._store.load_all():
            status = payload.get("status")
            if status in ("completed", "failed", "cancelled"):
                continue  # terminal — never resume
            task = CodingTask(**payload)
            try:
                self.validate_project(task.project_path)
            except AgentError as exc:
                task.status = "failed"
                task.phase = "FAILED"
                task.last_error = f"Recovery aborted (safety): {exc}"
                self._store.save(task.model_dump())
                results.append({"id": task.id, "status": task.status})
                continue
            if not task.checkpoint:
                task.status = "failed"
                task.phase = "FAILED"
                task.last_error = (
                    "Recovery aborted (safety): interrupted task has no checkpoint"
                )
                self._store.save(task.model_dump())
                results.append({"id": task.id, "status": task.status})
                continue
            recovered = await self._agent.recover(task)
            results.append({
                "id": recovered.id,
                "checkpoint": recovered.checkpoint,
                "status": recovered.status,
                "phase": recovered.phase,
            })
        return results