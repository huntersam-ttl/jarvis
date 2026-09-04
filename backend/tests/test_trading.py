"""Tests for the trading bridge: mock adapter, service, and API endpoints."""
import pytest
from fastapi.testclient import TestClient

from app.deps import get_trading_service
from app.main import create_app
from app.trading.mock import MockTradingAdapter
from app.trading.service import TradingService, build_trading_service


@pytest.fixture
def client():
    app = create_app()
    # One shared mock adapter per test for realistic stateful lifecycle.
    service = TradingService(MockTradingAdapter())
    app.dependency_overrides[get_trading_service] = lambda: service
    return TestClient(app)


def test_build_service_uses_mock_without_base_url():
    service = build_trading_service("", "")
    assert service.adapter_name == "mock"


def test_build_service_uses_http_with_base_url():
    service = build_trading_service("http://127.0.0.1:9999", "key")
    assert service.adapter_name == "http"


def test_status_defaults_offline(client):
    res = client.get("/api/trading/status")
    assert res.status_code == 200
    body = res.json()
    assert body["connected"] is True
    assert body["mode"] == "paper"
    assert body["state"] == "offline"
    assert body["open_positions"] == 0
    assert body["today_pnl"] == 0
    assert body["adapter"] == "mock"


def test_full_lifecycle(client):
    # start
    res = client.post("/api/trading/start")
    assert res.status_code == 200
    assert res.json()["state"] == "running"

    status = client.get("/api/trading/status").json()
    assert status["state"] == "running"
    assert status["open_positions"] >= 1

    positions = client.get("/api/trading/positions").json()
    assert isinstance(positions, list) and len(positions) >= 1
    for p in positions:
        assert set(p.keys()) == {
            "symbol",
            "side",
            "qty",
            "entry_price",
            "unrealized_pnl",
        }

    # pause
    assert client.post("/api/trading/pause").json()["state"] == "paused"
    # resume
    assert client.post("/api/trading/resume").json()["state"] == "running"
    # stop
    stop = client.post("/api/trading/stop").json()
    assert stop["success"] is True
    assert stop["state"] == "offline"

    status = client.get("/api/trading/status").json()
    assert status["open_positions"] == 0

    activity = client.get("/api/trading/activity").json()
    events = [a["event"] for a in activity]
    assert {"started", "paused", "resumed", "stopped"} <= set(events)


def test_invalid_transitions_rejected(client):
    # pause before start
    res = client.post("/api/trading/pause")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is False
    assert "Cannot pause" in body["detail"]


def test_performance_after_stop(client):
    client.post("/api/trading/start")
    client.post("/api/trading/stop")
    perf = client.get("/api/trading/performance").json()
    assert set(perf.keys()) == {"today_pnl", "total_pnl", "win_rate", "trades_today"}


def test_activity_limit(client):
    client.post("/api/trading/start")
    client.post("/api/trading/pause")
    client.post("/api/trading/resume")
    client.post("/api/trading/stop")
    res = client.get("/api/trading/activity?limit=2")
    assert res.status_code == 200
    assert len(res.json()) <= 2


def test_http_adapter_unreachable_status(monkeypatch):
    """HTTP adapter reports disconnected cleanly when the agent is down."""
    import httpx

    from app.trading.http_adapter import HTTPTradingAdapter

    def _fail(*args, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", _fail)

    adapter = HTTPTradingAdapter("http://127.0.0.1:9999")
    import asyncio

    status = asyncio.get_event_loop().run_until_complete(adapter.get_status())
    assert status.connected is False
    assert status.state == "offline"
    assert status.adapter == "http"
