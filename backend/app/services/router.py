"""Model router (v0).

v0 is intentionally simple: default provider = OmniRoute, default model from
environment. Each request records requested model, provider, duration, and
success/failure. Later phases add cost-aware and quality-aware routing.
"""
from __future__ import annotations

from typing import Optional

from app.core.logging import get_logger
from app.providers.base import Provider
from app.providers.omniroute import OmniRouteProvider

logger = get_logger("jarvis.services.router")


class ModelRouter:
    """Resolves a provider + model for a chat request."""

    def __init__(self, omniroute: OmniRouteProvider):
        self._omniroute = omniroute
        self._providers: dict[str, Provider] = {"omniroute": omniroute}

    @property
    def default_provider_name(self) -> str:
        return "omniroute"

    @property
    def default_model(self) -> str:
        return self._omniroute.default_model

    def get_provider(self, name: Optional[str] = None) -> Provider:
        provider_name = name or self.default_provider_name
        provider = self._providers.get(provider_name)
        if provider is None:
            raise KeyError(f"Unknown provider: {provider_name}")
        return provider

    def resolve_model(self, requested_model: Optional[str]) -> str:
        return requested_model or self.default_model
