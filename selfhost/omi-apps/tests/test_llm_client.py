import httpx
import pytest

from app.config import settings
from app.llm.client import LLMError, LLMClient


def _transport(primary_status: int = 200, primary_body: dict | None = None, fallback_status: int | None = None):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if "primary-key" in auth:
            calls.append("primary")
            status, body = primary_status, primary_body or {
                "choices": [{"message": {"content": "tra loi tu primary"}}]
            }
            return httpx.Response(status, json=body)
        if "fallback-key" in auth:
            calls.append("fallback")
            return httpx.Response(
                fallback_status or 200,
                json={"choices": [{"message": {"content": "tra loi tu fallback"}}]},
            )
        return httpx.Response(401, json={})

    return httpx.MockTransport(handler), calls


@pytest.fixture(autouse=True)
def primary_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_base_url", "https://primary.example/v1")
    monkeypatch.setattr(settings, "llm_api_key", "primary-key")
    monkeypatch.setattr(settings, "llm_model", "test-model")


@pytest.mark.asyncio
async def test_chat_success_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, _ = _transport()
    async with httpx.AsyncClient(transport=transport) as hc:
        client = LLMClient(http_client=hc)
        out = await client.chat([{"role": "user", "content": "xin chao"}])
    assert out == "tra loi tu primary"


@pytest.mark.asyncio
async def test_fallback_on_primary_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "fallback_llm_base_url", "https://fallback.example/v1")
    monkeypatch.setattr(settings, "fallback_llm_api_key", "fallback-key")
    transport, calls = _transport(primary_status=503)
    async with httpx.AsyncClient(transport=transport) as hc:
        client = LLMClient(http_client=hc)
        out = await client.chat([{"role": "user", "content": "xin chao"}])
    assert out == "tra loi tu fallback"
    assert calls == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_no_fallback_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "fallback_llm_base_url", "")
    transport, calls = _transport(primary_status=500)
    async with httpx.AsyncClient(transport=transport) as hc:
        client = LLMClient(http_client=hc)
        with pytest.raises(LLMError):
            await client.chat([{"role": "user", "content": "xin chao"}])
    assert calls == ["primary"]


@pytest.mark.asyncio
async def test_4xx_does_not_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "fallback_llm_base_url", "https://fallback.example/v1")
    monkeypatch.setattr(settings, "fallback_llm_api_key", "fallback-key")
    transport, calls = _transport(primary_status=401)
    async with httpx.AsyncClient(transport=transport) as hc:
        client = LLMClient(http_client=hc)
        with pytest.raises(LLMError):
            await client.chat([{"role": "user", "content": "xin chao"}])
    assert calls == ["primary"]


@pytest.mark.asyncio
async def test_malformed_response_raises() -> None:
    transport, _ = _transport(primary_body={"weird": True})
    async with httpx.AsyncClient(transport=transport) as hc:
        client = LLMClient(http_client=hc)
        with pytest.raises(LLMError):
            await client.chat([{"role": "user", "content": "xin chao"}])
