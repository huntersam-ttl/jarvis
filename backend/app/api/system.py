"""System status endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.deps import get_openrouter_provider
from app.models.schemas import SystemComponent, SystemStatus
from app.providers.openrouter import OpenRouterProvider

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status", response_model=SystemStatus)
async def system_status(
    openrouter: OpenRouterProvider = Depends(get_openrouter_provider),
) -> SystemStatus:
    settings = get_settings()

    components = [
        SystemComponent(name="Backend", status="online", detail="FastAPI running"),
        SystemComponent(name="Frontend", status="online", detail="Next.js Control Room"),
    ]

    # OpenRouter
    if not openrouter.configured:
        components.append(
            SystemComponent(
                name="OpenRouter",
                status="not_configured",
                detail="OPENROUTER_API_KEY missing in .env",
            )
        )
    else:
        reachable = await openrouter.health_check()
        components.append(
            SystemComponent(
                name="OpenRouter",
                status="connected" if reachable else "offline",
                detail=settings.openrouter_base_url,
            )
        )

    # AI provider (same as OpenRouter in v0)
    ai_status = "online" if openrouter.configured else "not_configured"
    components.append(
        SystemComponent(
            name="AI Provider",
            status=ai_status,
            detail=f"model={settings.openrouter_default_model}",
        )
    )

    components.append(SystemComponent(name="Tasks", status="ready", detail="v0 run tracking"))

    overall = "online"
    if any(c.status in ("offline", "not_configured") for c in components):
        overall = "degraded"

    return SystemStatus(overall=overall, components=components)
