"""Tests for the OmniRoute provider using a mocked HTTP transport."""
import httpx
import pytest

from app.core.exceptions import ProviderNotConfiguredError, ProviderResponseError
from app.models.schemas import ProviderModel
from app.providers.omniroute import OmniRouteProvider


def _patch_client(monkeypatch, transport: httpx.MockTransport):
    """Patch httpx.AsyncClient so OmniRouteProvider uses our transport."""
    orig = httpx.AsyncClient

    def _client(*args, **kwargs):
        kwargs["transport"] = transport
        return orig(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client)


@pytest.mark.asyncio
async def test_not_configured_raises(monkeypatch):
    provider = OmniRouteProvider(base_url="http://x/v1", api_key="", default_model="auto/glm")
    assert provider.configured is False
    with pytest.raises(ProviderNotConfiguredError):
        await provider.list_models()
    with pytest.raises(ProviderNotConfiguredError):
        await provider.chat("hi")


@pytest.mark.asyncio
async def test_health_check_ok(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": []})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OmniRouteProvider("http://127.0.0.1:20128/v1", "test-key", "auto/glm")
    assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_health_check_unreachable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OmniRouteProvider("http://127.0.0.1:20128/v1", "test-key", "auto/glm")
    assert await provider.health_check() is False


@pytest.mark.asyncio
async def test_list_models(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "auto/glm", "owned_by": "zai"}, {"id": "gpt-4o"}]},
        )

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OmniRouteProvider("http://127.0.0.1:20128/v1", "test-key", "auto/glm")
    models = await provider.list_models()
    assert models == [ProviderModel(id="auto/glm", owned_by="zai"), ProviderModel(id="gpt-4o")]


@pytest.mark.asyncio
async def test_list_models_error_status(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OmniRouteProvider("http://127.0.0.1:20128/v1", "test-key", "auto/glm")
    with pytest.raises(ProviderResponseError):
        await provider.list_models()


@pytest.mark.asyncio
async def test_chat(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b'"model":"auto/glm"' in body
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Hello from Jarvis"}}]},
        )

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OmniRouteProvider("http://127.0.0.1:20128/v1", "test-key", "auto/glm")
    reply, model = await provider.chat("Hello Jarvis")
    assert reply == "Hello from Jarvis"
    assert model == "auto/glm"


@pytest.mark.asyncio
async def test_chat_no_choices(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OmniRouteProvider("http://127.0.0.1:20128/v1", "test-key", "auto/glm")
    with pytest.raises(ProviderResponseError):
        await provider.chat("hi")


@pytest.mark.asyncio
async def test_get_model_info(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "auto/glm", "owned_by": "zai"}]})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OmniRouteProvider("http://127.0.0.1:20128/v1", "test-key", "auto/glm")
    info = await provider.get_model_info("auto/glm")
    assert info == {"id": "auto/glm", "owned_by": "zai", "available": True}
    missing = await provider.get_model_info("nope")
    assert missing["available"] is False
