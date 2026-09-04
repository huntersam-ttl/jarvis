"""Health endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", version="0.1.0", environment=settings.jarvis_env)
