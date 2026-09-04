"""Generic provider interface.

Any OpenAI-compatible provider (OpenAI, DeepSeek, MiniMax, Anthropic, ...)
can be added by implementing this interface. Jarvis core never changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from app.models.schemas import ProviderModel


class Provider(ABC):
    """Abstract provider. Implementations talk to a concrete AI gateway."""

    name: str

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider endpoint is reachable and configured."""

    @abstractmethod
    async def list_models(self) -> List[ProviderModel]:
        """Return available models from the provider."""

    @abstractmethod
    async def chat(
        self,
        message: str,
        model: Optional[str] = None,
    ) -> tuple[str, str]:
        """Send a single-turn chat. Return (reply_text, resolved_model)."""

    @abstractmethod
    async def get_model_info(self, model: str) -> dict:
        """Return normalized info about a model."""

    @property
    def default_model(self) -> str:
        return getattr(self, "_default_model", "")
