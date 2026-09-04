"""Coding Agent endpoints — status, tasks, project registry, cancel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.agents.base import AgentError
from app.agents.coding.schemas import (
    CancelResult,
    CodingAgentStatus,
    CodingTask,
    CreateCodingTaskRequest,
    ProjectRegistryResponse,
)
from app.agents.coding.service import CodingAgentService
from app.deps import get_coding_agent_service

router = APIRouter(prefix="/api/agents/coding", tags=["agents"])


def _service(
    service: CodingAgentService = Depends(get_coding_agent_service),
) -> CodingAgentService:
    return service


def _agent_error(exc: AgentError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/status", response_model=CodingAgentStatus)
async def coding_status(
    service: CodingAgentService = Depends(_service),
) -> CodingAgentStatus:
    snapshot = await service.status()
    return CodingAgentStatus(
        status=snapshot["status"],
        has_active_task=snapshot["has_active_task"],
        task=snapshot["task"],
        allowed_projects=service.allowed_projects,
    )


@router.get("/projects", response_model=ProjectRegistryResponse)
async def coding_projects(
    service: CodingAgentService = Depends(_service),
) -> ProjectRegistryResponse:
    return ProjectRegistryResponse(projects=service.allowed_projects)


@router.post("/tasks", response_model=CodingTask, status_code=202)
async def create_coding_task(
    request: CreateCodingTaskRequest,
    service: CodingAgentService = Depends(_service),
) -> CodingTask:
    try:
        return await service.submit(
            instruction=request.instruction,
            project_path=request.project_path,
            model=request.model,
            max_steps=request.max_steps,
            approve_destructive=request.approve_destructive,
        )
    except AgentError as exc:
        raise _agent_error(exc) from exc


@router.get("/tasks/{task_id}", response_model=CodingTask)
async def get_coding_task(
    task_id: str,
    service: CodingAgentService = Depends(_service),
) -> CodingTask:
    try:
        return await service.task(task_id)
    except AgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/cancel", response_model=CancelResult)
async def cancel_coding_task(
    task_id: str,
    service: CodingAgentService = Depends(_service),
) -> CancelResult:
    try:
        task = await service.cancel(task_id)
    except AgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CancelResult(success=True, status=task.status, detail="Cancellation requested")