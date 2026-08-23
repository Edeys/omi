import httpx
import pytest

from app.config import settings
from app.notifications.sender import NotificationSender


@pytest.fixture(autouse=True)
def notify_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "backend_url", "https://omi-api.example")
    monkeypatch.setattr(settings, "admin_key", "test-admin-key")
    monkeypatch.setattr(settings, "notify_min_gap_seconds", 60)


@pytest.mark.asyncio
async def test_send_success_payload_shape() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["json"] = request.read()
        return httpx.Response(200, json={"status": "Ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as hc:
        sender = NotificationSender(http_client=hc)
        ok = await sender.send("u1", "Tieu de", "Noi dung thong bao", {"session": "s1"})
    assert ok is True
    assert seen["url"].endswith("/v1/notification")
    assert seen["headers"]["secret-key"] == "test-admin-key"
    body = seen["json"].decode()
    assert '"uid":"u1"' in body.replace(" ", "") or '"uid": "u1"' in body
    assert "Noi dung thong bao" in body


@pytest.mark.asyncio
async def test_missing_config_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_key", "")
    async with httpx.AsyncClient() as hc:
        sender = NotificationSender(http_client=hc)
        ok = await sender.send("u1", "t", "m")
    assert ok is False


@pytest.mark.asyncio
async def test_gap_throttle_blocks_second_send() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"status": "Ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as hc:
        sender = NotificationSender(http_client=hc)
        first = await sender.send("u2", "t", "first message")
        second = await sender.send("u2", "t", "second message within gap")
    assert first is True
    assert second is False
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_transport_error_returns_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as hc:
        sender = NotificationSender(http_client=hc)
        ok = await sender.send("u3", "t", "message body")
    assert ok is False


@pytest.mark.asyncio
async def test_4xx_returns_false_without_marking_sent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "nope"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as hc:
        sender = NotificationSender(http_client=hc)
        ok = await sender.send("u4", "t", "message body")
        retry = await sender.send("u4", "t", "message body")
    assert ok is False
    assert retry is False
