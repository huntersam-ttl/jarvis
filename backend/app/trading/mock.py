"""Mock trading adapter — in-memory simulated agent for development.

Used when TRADING_AGENT_BASE_URL is not configured so the Trading Control
Room is fully functional before the real trading-agent API exists.
No real broker execution ever happens here.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
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

logger = get_logger("jarvis.trading.mock")

_VALID_COMMANDS = {"start", "pause", "resume", "stop"}


class MockTradingAdapter(TradingAdapter):
    name = "mock"

    def __init__(self, mode: str = "paper"):
        self._mode = mode
        self._state = "offline"
        self._positions: List[TradingPosition] = []
        self._today_pnl = 0.0
        self._total_pnl = 0.0
        self._trades_today = 0
        self._last_heartbeat: str | None = None
        self._activity: List[TradingActivityItem] = []

    # ---- helpers -------------------------------------------------------
    def _log(self, event: str, detail: str | None = None) -> None:
        self._activity.insert(
            0,
            TradingActivityItem(
                id=uuid.uuid4().hex,
                time=datetime.now(timezone.utc).isoformat(),
                event=event,
                detail=detail,
            ),
        )
        self._activity = self._activity[:50]
        self._last_heartbeat = datetime.now(timezone.utc).isoformat()

    def _simulate_tick(self) -> None:
        """Advance the simulated world slightly while running."""
        if self._state != "running" or not self._positions:
            return
        for pos in self._positions:
            delta = round(random.uniform(-40, 45), 2)
            pos.unrealized_pnl = round(pos.unrealized_pnl + delta, 2)
        self._today_pnl = round(
            sum(p.unrealized_pnl for p in self._positions), 2
        )
        self._last_heartbeat = datetime.now(timezone.utc).isoformat()

    # ---- interface -----------------------------------------------------
    async def get_status(self) -> TradingStatus:
        self._simulate_tick()
        return TradingStatus(
            connected=True,
            mode=self._mode,
            state=self._state,
            open_positions=len(self._positions),
            today_pnl=self._today_pnl,
            last_heartbeat=self._last_heartbeat,
            adapter=self.name,
        )

    async def get_positions(self) -> List[TradingPosition]:
        self._simulate_tick()
        return list(self._positions)

    async def get_activity(self, limit: int = 20) -> List[TradingActivityItem]:
        return self._activity[:limit]

    async def get_performance(self) -> TradingPerformance:
        return TradingPerformance(
            today_pnl=self._today_pnl,
            total_pnl=self._total_pnl,
            win_rate=None,
            trades_today=self._trades_today,
        )

    async def send_command(self, command: TradingCommand) -> TradingCommandResult:
        command = (command or "").strip().lower()
        if command not in _VALID_COMMANDS:
            return TradingCommandResult(
                success=False, state=self._state, detail=f"Unknown command: {command}"
            )

        if command == "start":
            if self._state != "offline":
                return TradingCommandResult(
                    success=False,
                    state=self._state,
                    detail=f"Cannot start from state '{self._state}'",
                )
            self._state = "running"
            self._positions = [
                TradingPosition(
                    symbol="BTC/USDT",
                    side="long",
                    qty=0.05,
                    entry_price=64200.0,
                    unrealized_pnl=0.0,
                ),
                TradingPosition(
                    symbol="ETH/USDT",
                    side="short",
                    qty=0.8,
                    entry_price=3150.0,
                    unrealized_pnl=0.0,
                ),
            ]
            self._log("started", "mock agent started in paper mode")
            logger.info("mock trading agent started")
        elif command == "pause":
            if self._state != "running":
                return TradingCommandResult(
                    success=False,
                    state=self._state,
                    detail=f"Cannot pause from state '{self._state}'",
                )
            self._state = "paused"
            self._log("paused", "positions held, no new entries")
        elif command == "resume":
            if self._state != "paused":
                return TradingCommandResult(
                    success=False,
                    state=self._state,
                    detail=f"Cannot resume from state '{self._state}'",
                )
            self._state = "running"
            self._log("resumed", "agent resumed")
        elif command == "stop":
            if self._state == "offline":
                return TradingCommandResult(
                    success=False,
                    state=self._state,
                    detail="Agent already offline",
                )
            closed_pnl = round(sum(p.unrealized_pnl for p in self._positions), 2)
            closed_count = len(self._positions)
            self._total_pnl = round(self._total_pnl + closed_pnl, 2)
            self._trades_today += closed_count
            self._positions = []
            self._state = "offline"
            self._log(
                "stopped",
                f"closed {closed_count} positions, session pnl={closed_pnl}",
            )

        return TradingCommandResult(success=True, state=self._state)
