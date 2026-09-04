"""Generic TradingAdapter interface.

The real trading agent is a separate project. Jarvis only needs a small,
normalized surface: status, positions, activity, performance and the four
lifecycle commands. Any backend (HTTP API, local process, future message
bus) can be plugged in by implementing this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.models.schemas import (
    TradingActivityItem,
    TradingCommandResult,
    TradingPerformance,
    TradingPosition,
    TradingStatus,
)

# Commands understood by every adapter.
TradingCommand = str  # "start" | "pause" | "resume" | "stop"


class TradingAdapter(ABC):
    """Abstract trading backend adapter."""

    name: str = "base"

    @abstractmethod
    async def get_status(self) -> TradingStatus:
        """Return normalized connection/run status."""

    @abstractmethod
    async def get_positions(self) -> List[TradingPosition]:
        """Return currently open positions."""

    @abstractmethod
    async def get_activity(self, limit: int = 20) -> List[TradingActivityItem]:
        """Return most recent activity events (newest first)."""

    @abstractmethod
    async def get_performance(self) -> TradingPerformance:
        """Return normalized performance metrics."""

    @abstractmethod
    async def send_command(self, command: TradingCommand) -> TradingCommandResult:
        """Send a lifecycle command: start | pause | resume | stop."""
