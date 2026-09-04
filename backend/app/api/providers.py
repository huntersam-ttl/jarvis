"""Provider management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.core.exceptions import ProviderError
from app.deps import get_openrouter_provider
from app.models.schemas import ProviderInfo, ProviderList, ProviderModelList
from app.providers.openrouter import OpenRouterProvider

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=ProviderList)
async def list_providers(
    openrouter: OpenRouterProvider = Depends(get_openrouter_provider),
) -> ProviderList:
    settings = get_settings()

    if not openrouter.configured:
        info = ProviderInfo(
            name="openrouter",
            status="not_configured",
            base_url=settings.openrouter_base_url,
            default_model=settings.openrouter_default_model,
            model_count=0,
            api_key_configured=False,
        )
    else:
        reachable = await openrouter.health_check()
        model_count = 0
        if reachable:
            try:
                model_count = len(await openrouter.list_models())
            except ProviderError:
                model_count = 0
        info = ProviderInfo(
            name="openrouter",
            status="connected" if reachable else "offline",
            base_url=settings.openrouter_base_url,
            default_model=settings.openrouter_default_model,
            model_count=model_count,
            api_key_configured=True,
        )

    return ProviderList(providers=[info])


@router.get("/openrouter/models", response_model=ProviderModelList)
async def list_openrouter_models(
    openrouter: OpenRouterProvider = Depends(get_openrouter_provider),
) -> ProviderModelList:
    try:
        models = await openrouter.list_models()
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ProviderModelList(provider="openrouter", models=models, count=len(models))
