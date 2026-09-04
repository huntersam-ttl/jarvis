"""Provider management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.core.exceptions import ProviderError
from app.deps import get_omniroute_provider
from app.models.schemas import ProviderInfo, ProviderList, ProviderModelList
from app.providers.omniroute import OmniRouteProvider

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=ProviderList)
async def list_providers(
    omniroute: OmniRouteProvider = Depends(get_omniroute_provider),
) -> ProviderList:
    settings = get_settings()

    if not omniroute.configured:
        info = ProviderInfo(
            name="omniroute",
            status="not_configured",
            base_url=settings.omniroute_base_url,
            default_model=settings.omniroute_default_model,
            model_count=0,
            api_key_configured=False,
        )
    else:
        reachable = await omniroute.health_check()
        model_count = 0
        if reachable:
            try:
                model_count = len(await omniroute.list_models())
            except ProviderError:
                model_count = 0
        info = ProviderInfo(
            name="omniroute",
            status="connected" if reachable else "offline",
            base_url=settings.omniroute_base_url,
            default_model=settings.omniroute_default_model,
            model_count=model_count,
            api_key_configured=True,
        )

    return ProviderList(providers=[info])


@router.get("/omniroute/models", response_model=ProviderModelList)
async def list_omniroute_models(
    omniroute: OmniRouteProvider = Depends(get_omniroute_provider),
) -> ProviderModelList:
    try:
        models = await omniroute.list_models()
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ProviderModelList(provider="omniroute", models=models, count=len(models))
