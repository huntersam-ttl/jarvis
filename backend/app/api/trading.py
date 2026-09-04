"""Trading bridge endpoints — control and monitoring of the trading agent."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_trading_service
from app.models.schemas import (
    TradingActivityItem,
    TradingCommandResult,
    TradingPerformance,
    TradingPosition,
    TradingStatus,
)
from app.trading.http_adapter import TradingAgentUnreachableError
from app.trading.service import TradingService

router = APIRouter(prefix="/api/trading", tags=["trading"])


def _unreachable(exc: TradingAgentUnreachableError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/status", response_model=TradingStatus)
async def trading_status(
    service: TradingService = Depends(get_trading_service),
) -> TradingStatus:
    try:
        return await service.status()
    except TradingAgentUnreachableError as exc:
        raise _unreachable(exc) from exc


@router.get("/positions", response_model=list[TradingPosition])
async def trading_positions(
    service: TradingService = Depends(get_trading_service),
) -> list[TradingPosition]:
    try:
        return await service.positions()
    except TradingAgentUnreachableError as exc:
        raise _unreachable(exc) from exc


@router.get("/activity", response_model=list[TradingActivityItem])
async def trading_activity(
    limit: int = 20,
    service: TradingService = Depends(get_trading_service),
) -> list[TradingActivityItem]:
    try:
        return await service.activity(limit=min(max(limit, 1), 50))
    except TradingAgentUnreachableError as exc:
        raise _unreachable(exc) from exc


@router.get("/performance", response_model=TradingPerformance)
async def trading_performance(
    service: TradingService = Depends(get_trading_service),
) -> TradingPerformance:
    try:
        return await service.performance()
    except TradingAgentUnreachableError as exc:
        raise _unreachable(exc) from exc


async def _run_command(
    command: str, service: TradingService
) -> TradingCommandResult:
    try:
        return await service.command(command)
    except TradingAgentUnreachableError as exc:
        raise _unreachable(exc) from exc


@router.post("/start", response_model=TradingCommandResult)
async def trading_start(
    service: TradingService = Depends(get_trading_service),
) -> TradingCommandResult:
    return await _run_command("start", service)


@router.post("/pause", response_model=TradingCommandResult)
async def trading_pause(
    service: TradingService = Depends(get_trading_service),
) -> TradingCommandResult:
    return await _run_command("pause", service)


@router.post("/resume", response_model=TradingCommandResult)
async def trading_resume(
    service: TradingService = Depends(get_trading_service),
) -> TradingCommandResult:
    return await _run_command("resume", service)


@router.post("/stop", response_model=TradingCommandResult)
async def trading_stop(
    service: TradingService = Depends(get_trading_service),
) -> TradingCommandResult:
    return await _run_command("stop", service)
