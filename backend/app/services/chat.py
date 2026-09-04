"""Chat service — orchestrates a chat request through the model router.

Records run metadata (requested model, provider, duration, success/failure)
and returns a normalized ChatResponse. Raw provider JSON is never leaked.
"""
from __future__ import annotations

from typing import Optional

from app.core.exceptions import ChatError, ProviderError
from app.core.logging import get_logger
from app.core.timing import timed
from app.models.schemas import ChatResponse, ChatRunMeta
from app.services.router import ModelRouter

logger = get_logger("jarvis.services.chat")


class ChatService:
    def __init__(self, router: ModelRouter):
        self._router = router

    async def handle(self, message: str, model: Optional[str] = None) -> ChatResponse:
        requested_model = model
        resolved_model = self._router.resolve_model(model)
        provider = self._router.get_provider()
        provider_name = provider.name

        with timed() as t:
            try:
                reply, used_model = await provider.chat(message, model=resolved_model)
                success = True
            except ProviderError as exc:
                logger.warning("chat failed via %s: %s", provider_name, exc)
                reply = ""
                used_model = resolved_model
                success = False
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("unexpected chat error via %s", provider_name)
                reply = ""
                used_model = resolved_model
                success = False

        run = ChatRunMeta(
            requested_model=requested_model,
            resolved_model=used_model,
            provider=provider_name,
            duration_ms=t.get("duration_ms", 0.0),
            success=success,
        )

        if not success:
            raise ChatError(f"Jarvis could not complete the request via {provider_name}")

        return ChatResponse(
            reply=reply,
            model=used_model,
            provider=provider_name,
            status="completed",
            run=run,
        )
