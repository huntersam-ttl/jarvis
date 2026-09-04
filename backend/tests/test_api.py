"""Tests for the API layer using FastAPI TestClient with dependency overrides."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ProviderResponseError
from app.deps import get_chat_service, get_openrouter_provider
from app.main import create_app
from app.models.schemas import ChatResponse, ChatRunMeta
from app.providers.openrouter import OpenRouterProvider
from app.services.chat import ChatService
from app.services.router import ModelRouter


class FakeProvider(OpenRouterProvider):
    """A fake OpenRouter provider that doesn't hit the network."""

    def __init__(self, *, configured=True, models=None, reply="Hello from Jarvis", fail=False):
        super().__init__("http://fake/v1", "key" if configured else "", "openai/gpt-4o-mini")
        self._fake_models = models or [{"id": "openai/gpt-4o-mini", "owned_by": "zai"}]
        self._reply = reply
        self._fail = fail

    async def health_check(self) -> bool:
        return self.configured and not self._fail

    async def list_models(self):
        if not self.configured:
            raise ProviderResponseError("not configured")
        if self._fail:
            raise ProviderResponseError("boom")
        from app.models.schemas import ProviderModel

        return [ProviderModel(id=m["id"], owned_by=m.get("owned_by")) for m in self._fake_models]

    async def chat(self, message, model=None):
        if self._fail:
            raise ProviderResponseError("chat failed")
        return self._reply, model or self._default_model


def _override_app(provider: FakeProvider):
    app = create_app()
    router = ModelRouter(provider)
    chat_service = ChatService(router)

    app.dependency_overrides[get_openrouter_provider] = lambda: provider
    app.dependency_overrides[get_chat_service] = lambda: chat_service
    return app


@pytest.fixture
def client_configured():
    provider = FakeProvider(configured=True)
    return TestClient(_override_app(provider)), provider


@pytest.fixture
def client_not_configured():
    provider = FakeProvider(configured=False)
    return TestClient(_override_app(provider)), provider


@pytest.fixture
def client_failing():
    provider = FakeProvider(configured=True, fail=True)
    return TestClient(_override_app(provider)), provider


def test_health(client_configured):
    client, _ = client_configured
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_system_status(client_configured):
    client, _ = client_configured
    res = client.get("/api/system/status")
    assert res.status_code == 200
    body = res.json()
    names = {c["name"] for c in body["components"]}
    assert {"Backend", "Frontend", "OpenRouter", "AI Provider", "Tasks"} <= names
    assert body["overall"] in ("online", "degraded")


def test_providers_configured(client_configured):
    client, _ = client_configured
    res = client.get("/api/providers")
    assert res.status_code == 200
    body = res.json()
    p = body["providers"][0]
    assert p["name"] == "openrouter"
    assert p["status"] == "connected"
    assert p["api_key_configured"] is True
    # The actual key must never appear
    assert "key" not in str(body).lower().replace("api_key_configured", "").replace("configured", "")


def test_providers_not_configured(client_not_configured):
    client, _ = client_not_configured
    res = client.get("/api/providers")
    assert res.status_code == 200
    p = res.json()["providers"][0]
    assert p["status"] == "not_configured"
    assert p["api_key_configured"] is False


def test_openrouter_models(client_configured):
    client, _ = client_configured
    res = client.get("/api/providers/openrouter/models")
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "openrouter"
    assert body["count"] == 1
    assert body["models"][0]["id"] == "openai/gpt-4o-mini"


def test_openrouter_models_failure(client_failing):
    client, _ = client_failing
    res = client.get("/api/providers/openrouter/models")
    assert res.status_code == 502


def test_chat_success(client_configured):
    client, _ = client_configured
    res = client.post("/api/chat", json={"message": "Hello Jarvis", "model": None})
    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "Hello from Jarvis"
    assert body["status"] == "completed"
    assert body["provider"] == "openrouter"
    assert body["run"]["success"] is True
    assert body["run"]["duration_ms"] >= 0


def test_chat_failure(client_failing):
    client, _ = client_failing
    res = client.post("/api/chat", json={"message": "Hello Jarvis"})
    assert res.status_code == 502


def test_chat_validation_empty_message(client_configured):
    client, _ = client_configured
    res = client.post("/api/chat", json={"message": ""})
    assert res.status_code == 422


def test_chat_no_raw_provider_json(client_configured):
    """Ensure normalized response does not leak raw provider fields."""
    client, _ = client_configured
    res = client.post("/api/chat", json={"message": "Hello Jarvis"})
    body = res.json()
    # Allowed top-level keys only
    assert set(body.keys()) == {"reply", "model", "provider", "status", "run"}
    assert set(body["run"].keys()) == {
        "requested_model",
        "resolved_model",
        "provider",
        "duration_ms",
        "success",
    }
