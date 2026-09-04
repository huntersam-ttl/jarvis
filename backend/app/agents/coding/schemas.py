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


class PlanStepModel(BaseModel):
    title: str
    verify: str = ""


class TaskPlan(BaseModel):
    objective: str = ""
    complexity: str = "SMALL"  # TRIVIAL | SMALL | MEDIUM | LARGE
    assumptions: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    steps: List[PlanStepModel] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    verification: List[str] = Field(default_factory=list)
    rollback: str = ""


class VerificationCheckModel(BaseModel):
    command: str
    ok: bool
    output: str = ""
    duration_ms: float = 0.0


class VerificationResultModel(BaseModel):
    passed: bool
    summary: str = ""
    checks: List[VerificationCheckModel] = Field(default_factory=list)


class ReviewFindingModel(BaseModel):
    severity: str
    file: str = "?"
    issue: str = ""
    suggestion: str = ""


class ReviewResultModel(BaseModel):
    verdict: str = "skipped"  # approve | block | skipped
    summary: str = ""
    findings: List[ReviewFindingModel] = Field(default_factory=list)


class CodingTask(BaseModel):
    id: str
    status: str  # ready | working | completed | failed | cancelled
    phase: str = "QUEUED"
    # QUEUED RECOVERING ANALYZING PLANNING IMPLEMENTING TESTING DEBUGGING
    # REVIEWING VERIFYING COMPLETED FAILED CANCELLED WAITING_APPROVAL
    checkpoint: str = ""
    # TASK_CREATED ANALYSIS_COMPLETE PLAN_COMPLETE FILES_CHANGED
    # VERIFICATION_COMPLETE REVIEW_COMPLETE COMPLETED
    current_task: str
    project_path: str
    started_at: str
    finished_at: Optional[str] = None
    last_error: Optional[str] = None
    actions: List[ActionRecord] = Field(default_factory=list)
    result: Optional[str] = None
    steps_taken: int = 0
    # engineering-agent extensions
    skills_used: List[str] = Field(default_factory=list)
    plan: Optional[TaskPlan] = None
    verification: Optional[VerificationResultModel] = None
    review: Optional[ReviewResultModel] = None
    repair_loops: int = 0
    model_calls: int = 0
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    git_commit: Optional[str] = None
    # recovery metadata
    git_branch: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)


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
    # Engineering-agent cost controls
    max_repair_loops: int = Field(default=2, ge=0, le=5)
    max_reviewer_calls: int = Field(default=1, ge=0, le=3)
    max_cost_usd: Optional[float] = Field(default=None, ge=0)
    auto_commit: bool = True
    create_project: bool = False  # new-project scaffold flow


class CancelResult(BaseModel):
    success: bool
    status: str
    detail: Optional[str] = None


class ProjectRegistryResponse(BaseModel):
    projects: List[str]
