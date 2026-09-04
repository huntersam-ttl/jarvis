"""Dependency injection — single place that wires providers and services.

Keeps route handlers thin and makes the app testable (override these
dependencies in tests).
"""
from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.providers.openrouter import OpenRouterProvider
from app.services.chat import ChatService
from app.services.router import ModelRouter
from app.trading.service import TradingService, build_trading_service


@lru_cache
def get_openrouter_provider() -> OpenRouterProvider:
    settings: Settings = get_settings()
    return OpenRouterProvider(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        default_model=settings.openrouter_default_model,
    )


@lru_cache
def get_model_router() -> ModelRouter:
    return ModelRouter(get_openrouter_provider())


@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(get_model_router())


@lru_cache
def get_trading_service() -> "TradingService":
    settings: Settings = get_settings()
    return build_trading_service(
        trading_agent_base_url=settings.trading_agent_base_url,
        trading_agent_api_key=settings.trading_agent_api_key,
        default_mode=settings.trading_default_mode,
    )
