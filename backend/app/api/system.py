"""System status endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.deps import get_omniroute_provider
from app.models.schemas import SystemComponent, SystemStatus
from app.providers.omniroute import OmniRouteProvider

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status", response_model=SystemStatus)
async def system_status(
    omniroute: OmniRouteProvider = Depends(get_omniroute_provider),
) -> SystemStatus:
    settings = get_settings()

    components = [
        SystemComponent(name="Backend", status="online", detail="FastAPI running"),
        SystemComponent(name="Frontend", status="online", detail="Next.js Control Room"),
    ]

    # OmniRoute
    if not omniroute.configured:
        components.append(
            SystemComponent(
                name="OmniRoute",
                status="not_configured",
                detail="OMNIROUTE_API_KEY missing in .env",
            )
        )
    else:
        reachable = await omniroute.health_check()
        components.append(
            SystemComponent(
                name="OmniRoute",
                status="connected" if reachable else "offline",
                detail=settings.omniroute_base_url,
            )
        )

    # AI provider (same as OmniRoute in v0)
    ai_status = "online" if omniroute.configured else "not_configured"
    components.append(
        SystemComponent(
            name="AI Provider",
            status=ai_status,
            detail=f"model={settings.omniroute_default_model}",
        )
    )

    components.append(SystemComponent(name="Tasks", status="ready", detail="v0 run tracking"))

    overall = "online"
    if any(c.status in ("offline", "not_configured") for c in components):
        overall = "degraded"

    return SystemStatus(overall=overall, components=components)
