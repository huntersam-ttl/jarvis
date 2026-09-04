"""Tests for the OpenRouter provider using a mocked HTTP transport."""
import httpx
import pytest

from app.core.exceptions import ProviderNotConfiguredError, ProviderResponseError
from app.models.schemas import ProviderModel
from app.providers.openrouter import OpenRouterProvider


def _patch_client(monkeypatch, transport: httpx.MockTransport):
    """Patch httpx.AsyncClient so OpenRouterProvider uses our transport."""
    orig = httpx.AsyncClient

    def _client(*args, **kwargs):
        kwargs["transport"] = transport
        return orig(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client)


@pytest.mark.asyncio
async def test_not_configured_raises(monkeypatch):
    provider = OpenRouterProvider(
        base_url="http://x/v1", api_key="", default_model="openai/gpt-4o-mini"
    )
    assert provider.configured is False
    with pytest.raises(ProviderNotConfiguredError):
        await provider.list_models()
    with pytest.raises(ProviderNotConfiguredError):
        await provider.chat("hi")


@pytest.mark.asyncio
async def test_health_check_ok(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/models"
        return httpx.Response(200, json={"data": []})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        "https://openrouter.ai/api/v1", "test-key", "openai/gpt-4o-mini"
    )
    assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_health_check_unreachable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        "https://openrouter.ai/api/v1", "test-key", "openai/gpt-4o-mini"
    )
    assert await provider.health_check() is False


@pytest.mark.asyncio
async def test_list_models(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "openai/gpt-4o-mini", "owned_by": "openai"},
                    {"id": "anthropic/claude-3.5-sonnet"},
                ]
            },
        )

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        "https://openrouter.ai/api/v1", "test-key", "openai/gpt-4o-mini"
    )
    models = await provider.list_models()
    assert models == [
        ProviderModel(id="openai/gpt-4o-mini", owned_by="openai"),
        ProviderModel(id="anthropic/claude-3.5-sonnet", owned_by=None),
    ]


@pytest.mark.asyncio
async def test_list_models_error_status(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        "https://openrouter.ai/api/v1", "test-key", "openai/gpt-4o-mini"
    )
    with pytest.raises(ProviderResponseError):
        await provider.list_models()


@pytest.mark.asyncio
async def test_chat(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b'"model":"openai/gpt-4o-mini"' in body
        return httpx.Response(
            200,
            json={
                "model": "openai/gpt-4o-mini",
                "choices": [{"message": {"content": "Hello from Jarvis"}}],
            },
        )

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        "https://openrouter.ai/api/v1", "test-key", "openai/gpt-4o-mini"
    )
    reply, model = await provider.chat("Hello Jarvis")
    assert reply == "Hello from Jarvis"
    assert model == "openai/gpt-4o-mini"


@pytest.mark.asyncio
async def test_chat_no_choices(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        "https://openrouter.ai/api/v1", "test-key", "openai/gpt-4o-mini"
    )
    with pytest.raises(ProviderResponseError):
        await provider.chat("hi")


@pytest.mark.asyncio
async def test_get_model_info(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [{"id": "openai/gpt-4o-mini", "owned_by": "openai"}]}
        )

    _patch_client(monkeypatch, httpx.MockTransport(handler))
    provider = OpenRouterProvider(
        "https://openrouter.ai/api/v1", "test-key", "openai/gpt-4o-mini"
    )
    info = await provider.get_model_info("openai/gpt-4o-mini")
    assert info == {"id": "openai/gpt-4o-mini", "owned_by": "openai", "available": True}
    missing = await provider.get_model_info("nope")
    assert missing["available"] is False
