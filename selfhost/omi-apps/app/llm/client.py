import logging
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("omi-apps.llm")

CONNECT_TIMEOUT = 3.0
FIRST_BYTE_TIMEOUT = 20.0


class LLMError(Exception):
    pass


class ProviderRejectedError(LLMError):
    """Provider answered 4xx — retrying elsewhere will not help."""


class LLMClient:
    """OpenAI-compatible chat client with optional secondary provider fallback.

    Primary comes from settings (OMI_APPS_* falling back to the backend's
    OPENAI_*/OMI_MAIN_MODEL). Fallback activates only when configured and the
    primary failed with a transport error, timeout, or 5xx.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client

    async def _acquire(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(FIRST_BYTE_TIMEOUT, connect=CONNECT_TIMEOUT)
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 700,
    ) -> str:
        try:
            return await self._chat_one(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=model or settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except LLMError as primary_error:
            if isinstance(primary_error, ProviderRejectedError):
                raise
            if not settings.fallback_llm_base_url or not settings.fallback_llm_api_key:
                raise
            logger.warning("primary LLM failed (%s), trying fallback", type(primary_error).__name__)
            return await self._chat_one(
                base_url=settings.fallback_llm_base_url,
                api_key=settings.fallback_llm_api_key,
                model=model or settings.fallback_llm_model or settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

    async def _chat_one(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        if not base_url or not api_key:
            raise LLMError("LLM provider is not configured")
        client = await self._acquire()
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        started = time.monotonic()
        try:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise LLMError(f"transport error: {type(exc).__name__}") from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= 500 or response.status_code == 429:
            raise LLMError(f"provider returned {response.status_code}")
        if response.status_code >= 400:
            logger.error("LLM request rejected status=%d model=%s", response.status_code, model)
            raise ProviderRejectedError(f"provider rejected request with {response.status_code}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("malformed completion response") from exc
        logger.info("llm ok model=%s latency_ms=%d out_len=%d", model, elapsed_ms, len(content))
        return content


llm_client = LLMClient()
