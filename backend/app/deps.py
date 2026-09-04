"""Dependency injection — single place that wires providers and services.

Keeps route handlers thin and makes the app testable (override these
dependencies in tests).
"""
from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.providers.omniroute import OmniRouteProvider
from app.services.chat import ChatService
from app.services.router import ModelRouter


@lru_cache
def get_omniroute_provider() -> OmniRouteProvider:
    settings: Settings = get_settings()
    return OmniRouteProvider(
        base_url=settings.omniroute_base_url,
        api_key=settings.omniroute_api_key,
        default_model=settings.omniroute_default_model,
    )


@lru_cache
def get_model_router() -> ModelRouter:
    return ModelRouter(get_omniroute_provider())


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(get_model_router())
