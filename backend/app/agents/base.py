"""Generic agent interface.

All Jarvis agents (Coding, and future Research / Communication / Security
agents) implement this interface so Jarvis core can manage them uniformly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.core.exceptions import JarvisError


class AgentError(JarvisError):
    """Agent-level failure."""


class Agent(ABC):
    """Abstract Jarvis agent."""

    name: str

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the agent is able to accept work."""

    @abstractmethod
    async def status(self) -> dict:
        """Return a snapshot of the agent's current state."""

    @abstractmethod
    async def run(self, instruction: str, project_path: Optional[str] = None) -> str:
        """Execute a task and return a human-readable summary."""
