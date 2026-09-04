"""HTTP trading adapter — talks to the real trading-agent API.

The trading agent is a separate project. It is expected to expose an
OpenAI-of-trading-style, normalized JSON API under TRADING_AGENT_BASE_URL:

    GET  /status
    GET  /positions
    GET  /activity
    GET  /performance
    POST /commands/{start|pause|resume|stop}

If the agent's actual API differs, only the mapping in this file needs to
change — nothing else in Jarvis. The API key is sent as a bearer token and
never exposed to the frontend.
"""
from __future__ import annotations

from typing import List, Optional

import httpx

from app.core.logging import get_logger
from app.models.schemas import (
    TradingActivityItem,
    TradingCommandResult,
    TradingPerformance,
    TradingPosition,
    TradingStatus,
)
from app.trading.base import TradingAdapter, TradingCommand

logger = get_logger("jarvis.trading.http")

_TIMEOUT = 5.0


class TradingAgentUnreachableError(Exception):
    """Raised when the trading agent cannot be reached."""


class HTTPTradingAdapter(TradingAdapter):
    name = "http"

    def __init__(self, base_url: str, api_key: str = "", mode: str = "paper"):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._mode = mode

    @property
    def configured(self) -> bool:
        return bool(self._base_url)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _get(self, path: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}{path}", headers=self._headers()
                )
        except httpx.HTTPError as exc:
            raise TradingAgentUnreachableError(
                f"Trading agent unreachable at {self._base_url}"
            ) from exc
        if resp.status_code != 200:
            raise TradingAgentUnreachableError(
                f"Trading agent returned HTTP {resp.status_code} for {path}"
            )
        return resp.json()

    # ---- interface -----------------------------------------------------
    async def get_status(self) -> TradingStatus:
        try:
            data = await self._get("/status")
        except TradingAgentUnreachableError:
            return TradingStatus(
                connected=False,
                mode=self._mode,
                state="offline",
                adapter=self.name,
            )
        return TradingStatus(
            connected=bool(data.get("connected", True)),
            mode=data.get("mode", self._mode),
            state=data.get("state", "offline"),
            open_positions=int(data.get("open_positions", 0)),
            today_pnl=float(data.get("today_pnl", 0.0)),
            last_heartbeat=data.get("last_heartbeat"),
            adapter=self.name,
        )

    async def get_positions(self) -> List[TradingPosition]:
        data = await self._get("/positions")
        raw = data.get("positions", data) if isinstance(data, dict) else data
        positions: List[TradingPosition] = []
        for p in raw or []:
            if isinstance(p, dict) and p.get("symbol"):
                positions.append(
                    TradingPosition(
                        symbol=p["symbol"],
                        side=p.get("side", "long"),
                        qty=float(p.get("qty", 0)),
                        entry_price=float(p.get("entry_price", 0)),
                        unrealized_pnl=float(p.get("unrealized_pnl", 0)),
                    )
                )
        return positions

    async def get_activity(self, limit: int = 20) -> List[TradingActivityItem]:
        data = await self._get(f"/activity?limit={limit}")
        raw = data.get("activity", data) if isinstance(data, dict) else data
        items: List[TradingActivityItem] = []
        for a in raw or []:
            if isinstance(a, dict) and a.get("event"):
                items.append(
                    TradingActivityItem(
                        id=str(a.get("id", "")),
                        time=str(a.get("time", "")),
                        event=str(a["event"]),
                        detail=a.get("detail"),
                    )
                )
        return items[:limit]

    async def get_performance(self) -> TradingPerformance:
        data = await self._get("/performance")
        return TradingPerformance(
            today_pnl=float(data.get("today_pnl", 0.0)),
            total_pnl=float(data.get("total_pnl", 0.0)),
            win_rate=data.get("win_rate"),
            trades_today=int(data.get("trades_today", 0)),
        )

    async def send_command(self, command: TradingCommand) -> TradingCommandResult:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/commands/{command}",
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            raise TradingAgentUnreachableError(
                f"Trading agent unreachable at {self._base_url}"
            ) from exc
        if resp.status_code not in (200, 202):
            return TradingCommandResult(
                success=False,
                state="error",
                detail=f"Trading agent returned HTTP {resp.status_code}",
            )
        data: Optional[dict] = None
        try:
            data = resp.json()
        except Exception:
            pass
        return TradingCommandResult(
            success=bool((data or {}).get("success", True)),
            state=str((data or {}).get("state", "unknown")),
            detail=(data or {}).get("detail"),
        )
