import logging
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("omi-apps.notifications")

CONNECT_TIMEOUT = 3.0
REQUEST_TIMEOUT = 10.0

_last_sent: dict[str, float] = {}


class NotificationSender:
    """Push notifications through the backend admin endpoint (/v1/notification).

    Client-side per-user gap throttle complements the backend's hourly cap.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client
        self._last_sent: dict[str, float] = {}

    async def _acquire(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    def _gap_ok(self, uid: str, now: float | None = None) -> bool:
        now = now or time.time()
        last = self._last_sent.get(uid)
        if last is not None and (now - last) < settings.notify_min_gap_seconds:
            return False
        return True

    async def send(self, uid: str, title: str, message: str, extra: dict[str, Any] | None = None) -> bool:
        if not settings.backend_url or not settings.admin_key:
            logger.warning("notifications disabled: backend_url or ADMIN_KEY missing")
            return False
        if not self._gap_ok(uid):
            logger.info("notification throttled for uid=%s (min gap %ds)", uid, settings.notify_min_gap_seconds)
            return False
        client = await self._acquire()
        payload = {
            "uid": uid,
            "title": title,
            "body": message,
            "data": extra or {},
        }
        try:
            response = await client.post(
                f"{settings.backend_url}/v1/notification",
                json=payload,
                headers={"secret-key": settings.admin_key},
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.warning("notification transport error: %s", type(exc).__name__)
            return False
        if response.status_code >= 400:
            logger.error("notification rejected status=%d", response.status_code)
            return False
        self._last_sent[uid] = time.time()
        logger.info("notification sent uid=%s len=%d", uid, len(message))
        return True


notification_sender = NotificationSender()
