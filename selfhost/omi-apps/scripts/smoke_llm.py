import asyncio
import sys
import time

from app.config import settings
from app.llm.client import LLMError, llm_client


async def main() -> int:
    if not settings.llm_base_url or not settings.llm_api_key:
        print("SMOKE_SKIP: LLM provider not configured")
        return 0
    started = time.monotonic()
    try:
        reply = await llm_client.chat(
            [{"role": "user", "content": "Trả lời đúng một từ: chào."}],
            max_tokens=30,
        )
    except LLMError as exc:
        print(f"SMOKE_FAIL: {exc}")
        return 1
    elapsed = int((time.monotonic() - started) * 1000)
    print(f"SMOKE_OK model={settings.llm_model} latency_ms={elapsed} reply_len={len(reply)}")
    await llm_client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
