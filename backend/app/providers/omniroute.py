"""OmniRoute provider — OpenAI-compatible local gateway.

OmniRoute runs locally via Docker at OMNIROUTE_BASE_URL.
The API key is read from settings and sent only as a bearer token to OmniRoute.
It is never printed, logged, or exposed to the frontend.
"""
from __future__ import annotations

from typing import List, Optional

import httpx

from app.core.exceptions import (
    ProviderNotConfiguredError,
    ProviderResponseError,
    ProviderUnreachableError,
)
from app.core.logging import get_logger
from app.models.schemas import ProviderModel
from app.providers.base import Provider

logger = get_logger("jarvis.providers.omniroute")


class OmniRouteProvider(Provider):
    name = "omniroute"

    def __init__(self, base_url: str, api_key: str, default_model: str = "auto/glm"):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._default_model = default_model

    # ---- helpers -------------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _ensure_configured(self) -> None:
        if not self.configured:
            raise ProviderNotConfiguredError(
                "OmniRoute API key is not configured. Set OMNIROUTE_API_KEY in .env"
            )

    # ---- interface -----------------------------------------------------
    async def health_check(self) -> bool:
        if not self.configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._base_url}/models", headers=self._headers()
                )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> List[ProviderModel]:
        self._ensure_configured()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._base_url}/models", headers=self._headers()
                )
        except httpx.HTTPError as exc:
            raise ProviderUnreachableError(
                f"Could not reach OmniRoute at {self._base_url}"
            ) from exc

        if resp.status_code != 200:
            raise ProviderResponseError(
                f"OmniRoute returned HTTP {resp.status_code}"
            )

        data = resp.json()
        raw = data.get("data", []) if isinstance(data, dict) else []
        models: List[ProviderModel] = []
        for m in raw:
            mid = m.get("id") if isinstance(m, dict) else None
            if mid:
                models.append(ProviderModel(id=mid, owned_by=m.get("owned_by")))
        return models

    async def chat(self, message: str, model: Optional[str] = None) -> tuple[str, str]:
        self._ensure_configured()
        resolved_model = model or self._default_model
        payload = {
            "model": resolved_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Jarvis, a concise, capable personal AI assistant. "
                        "Respond clearly and directly."
                    ),
                },
                {"role": "user", "content": message},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderUnreachableError(
                f"Could not reach OmniRoute at {self._base_url}"
            ) from exc

        if resp.status_code != 200:
            raise ProviderResponseError(
                f"OmniRoute chat returned HTTP {resp.status_code}"
            )

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderResponseError("OmniRoute returned no choices")
        reply = choices[0].get("message", {}).get("content", "")
        return reply.strip(), resolved_model

    async def get_model_info(self, model: str) -> dict:
        models = await self.list_models()
        for m in models:
            if m.id == model:
                return {"id": m.id, "owned_by": m.owned_by, "available": True}
        return {"id": model, "owned_by": None, "available": False}
