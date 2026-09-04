"""Jarvis backend — FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat as chat_api
from app.api import health as health_api
from app.api import providers as providers_api
from app.api import system as system_api
from app.api import trading as trading_api
from app.api import agents as agents_api
from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("jarvis.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "Jarvis backend starting | env=%s | openrouter=%s | model=%s | configured=%s",
        settings.jarvis_env,
        settings.openrouter_base_url,
        settings.openrouter_default_model,
        settings.openrouter_configured,
    )
    # Durable recovery: resume interrupted engineering tasks from SQLite.
    # Runs in the background so the API is immediately available.
    async def _recover():
        try:
            service = get_coding_agent_service()
            results = await service.recover_interrupted()
            if results:
                logger.info(f"recovered interrupted tasks: {results}")
        except Exception:
            logger.exception("task recovery failed")

    asyncio.create_task(_recover())
    yield
    logger.info("Jarvis backend shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Jarvis",
        description="Personal AI control system",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_api.router)
    app.include_router(system_api.router)
    app.include_router(providers_api.router)
    app.include_router(chat_api.router)
    app.include_router(trading_api.router)
    app.include_router(agents_api.router)

    return app


app = create_app()
