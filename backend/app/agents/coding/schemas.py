"""Schemas for the Coding Agent: task state, actions, and API payloads."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ActionRecord(BaseModel):
    """One deterministic tool action performed by the agent."""

    id: str
    step: int
    tool: str
    args_summary: str  # short human-readable summary, secrets never included
    ok: bool
    approval_required: bool = False
    detail: str = ""  # short result detail
    output_preview: str = ""  # truncated tool output for Advanced view
    started_at: str
    duration_ms: float = 0.0


class CodingTask(BaseModel):
    id: str
    status: str  # ready | working | completed | failed | cancelled
    current_task: str
    project_path: str
    started_at: str
    finished_at: Optional[str] = None
    last_error: Optional[str] = None
    actions: List[ActionRecord] = Field(default_factory=list)
    result: Optional[str] = None
    steps_taken: int = 0


class CodingAgentStatus(BaseModel):
    agent: str = "coding"
    status: str  # ready | working
    has_active_task: bool
    task: Optional[CodingTask] = None
    allowed_projects: List[str] = Field(default_factory=list)


class CreateCodingTaskRequest(BaseModel):
    instruction: str = Field(..., min_length=1)
    project_path: str = Field(..., min_length=1)
    model: Optional[str] = None
    max_steps: int = Field(default=12, ge=1, le=30)
    # Explicit approval for destructive operations (v1 escape hatch).
    approve_destructive: bool = False


class CancelResult(BaseModel):
    success: bool
    status: str
    detail: Optional[str] = None


class ProjectRegistryResponse(BaseModel):
    projects: List[str]
