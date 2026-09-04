"""Dependency injection — single place that wires providers and services.

Keeps route handlers thin and makes the app testable (override these
dependencies in tests).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import Settings, get_settings
from app.providers.openrouter import OpenRouterProvider
from app.services.chat import ChatService
from app.services.router import ModelRouter
from app.trading.service import TradingService, build_trading_service

if TYPE_CHECKING:
    from app.agents.coding.agent import CodingAgent
    from app.agents.coding.service import CodingAgentService
else:  # runtime import (kept lazy so chat paths stay light)
    from app.agents.coding.agent import CodingAgent
    from app.agents.coding.service import CodingAgentService, build_allowed_projects


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


_task_store = None  # created lazily on first persist


def _persist_task(task) -> None:
    """Persistence callback wired into the agent — never raises."""
    global _task_store
    try:
        if _task_store is None:
            from app.agents.coding.storage import TaskStore

            _task_store = TaskStore(
                Path(__file__).resolve().parents[1] / "jarvis_tasks.db"
            )
        _task_store.save(task.model_dump())
    except Exception:
        import logging

        logging.getLogger("jarvis.deps").exception("task persistence failed")


@lru_cache
def get_coding_agent() -> "CodingAgent":
    return CodingAgent(get_openrouter_provider(), on_update=_persist_task)


def get_task_store():
    """Lazily create the SQLite task store without writing probe rows."""
    global _task_store
    if _task_store is None:
        from app.agents.coding.storage import TaskStore

        _task_store = TaskStore(
            Path(__file__).resolve().parents[1] / "jarvis_tasks.db"
        )
    return _task_store


@lru_cache
def get_coding_agent_service() -> CodingAgentService:
    settings: Settings = get_settings()
    # Jarvis repo root = parent of the backend/ directory.
    jarvis_root = str(Path(__file__).resolve().parents[2])
    return CodingAgentService(
        agent=get_coding_agent(),
        allowed_projects=build_allowed_projects(
            settings.jarvis_allowed_projects, jarvis_root
        ),
        store=get_task_store(),
    )
