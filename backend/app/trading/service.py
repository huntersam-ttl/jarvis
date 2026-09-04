"""Trading service — selects the adapter and normalizes failures.

If TRADING_AGENT_BASE_URL is configured, the HTTPTradingAdapter talks to the
real trading agent. Otherwise the MockTradingAdapter keeps development usable.
Adapter failures are converted into clean, user-facing errors; raw provider
JSON never leaves this layer.
"""
from __future__ import annotations

from typing import List

from app.core.logging import get_logger
from app.models.schemas import (
    TradingActivityItem,
    TradingCommandResult,
    TradingPerformance,
    TradingPosition,
    TradingStatus,
)
from app.trading.base import TradingAdapter, TradingCommand
from app.trading.http_adapter import (
    HTTPTradingAdapter,
    TradingAgentUnreachableError,
)
from app.trading.mock import MockTradingAdapter

logger = get_logger("jarvis.trading.service")


class TradingService:
    def __init__(self, adapter: TradingAdapter):
        self._adapter = adapter

    @property
    def adapter_name(self) -> str:
        return self._adapter.name

    async def status(self) -> TradingStatus:
        return await self._adapter.get_status()

    async def positions(self) -> List[TradingPosition]:
        return await self._adapter.get_positions()

    async def activity(self, limit: int = 20) -> List[TradingActivityItem]:
        return await self._adapter.get_activity(limit)

    async def performance(self) -> TradingPerformance:
        return await self._adapter.get_performance()

    async def command(self, command: TradingCommand) -> TradingCommandResult:
        result = await self._adapter.send_command(command)
        if not result.success:
            logger.warning("trading command '%s' failed: %s", command, result.detail)
        return result


def build_trading_service(
    trading_agent_base_url: str,
    trading_agent_api_key: str,
    default_mode: str = "paper",
) -> TradingService:
    """Choose the adapter from environment configuration."""
    if (trading_agent_base_url or "").strip():
        adapter: TradingAdapter = HTTPTradingAdapter(
            base_url=trading_agent_base_url.strip(),
            api_key=(trading_agent_api_key or "").strip(),
            mode=default_mode,
        )
    else:
        adapter = MockTradingAdapter(mode=default_mode)
    return TradingService(adapter)
