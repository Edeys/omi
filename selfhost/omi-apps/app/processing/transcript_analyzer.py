import time
from typing import Any

from app.store.sessions import store as session_store

_memory_insights: dict[str, dict[str, Any]] = {}

REDIS_TTL = 24 * 3600


def _key(uid: str, session_id: str) -> str:
    return f"omi-apps:insight:{uid}:{session_id}"


class InsightStore:
    """Latest per-session insight with analysis bookkeeping.

    Falls back to in-process memory when Redis is unavailable, mirroring
    SessionStore semantics.
    """

    def __init__(self, redis_client: Any = None) -> None:
        self._redis = redis_client

    def _acquire(self) -> Any:
        if self._redis is None:
            try:
                from app.config import settings

                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    settings.redis_url, decode_responses=True
                )
            except Exception:
                self._redis = None
        return self._redis

    async def get(self, uid: str, session_id: str) -> dict[str, Any] | None:
        client = self._acquire()
        if client is not None:
            try:
                raw = await client.get(_key(uid, session_id))
                if raw:
                    import json

                    return json.loads(raw)
            except Exception:
                pass
        return _memory_insights.get(_key(uid, session_id))

    async def save(self, uid: str, session_id: str, record: dict[str, Any]) -> None:
        k = _key(uid, session_id)
        _memory_insights[k] = record
        client = self._acquire()
        if client is not None:
            try:
                import json

                await client.set(k, json.dumps(record), ex=REDIS_TTL)
            except Exception:
                pass


insight_store = InsightStore()


def unanalyzed_word_count(segments: list[dict[str, Any]], analyzed_upto: int) -> int:
    return sum(len(s.get("text", "").split()) for s in segments[analyzed_upto:])


async def record_for_analysis(
    uid: str,
    session_id: str,
    min_new_words: int,
    interval_seconds: int,
    now: float | None = None,
) -> bool:
    """Decide whether a fresh analysis should run for this session."""
    now = now or time.time()
    segments = await session_store.get_segments(uid, session_id)
    if not segments:
        return False
    previous = await insight_store.get(uid, session_id) or {}
    analyzed_upto = previous.get("analyzed_segments", 0)
    if len(segments) <= analyzed_upto:
        return False
    if unanalyzed_word_count(segments, analyzed_upto) < min_new_words:
        return False
    last_at = previous.get("created_at_ts", 0)
    return (now - last_at) >= interval_seconds


async def run_analysis(uid: str, session_id: str, llm_chat, prompt_builder=None) -> str | None:
    """Analyze buffered transcript via LLM and persist the insight.

    llm_chat is injected for testability; prompt_builder overridable too.
    Returns the insight text, or None when nothing to do / LLM failed.
    """
    from app.processing.prompts import build_transcript_insight_prompt

    builder = prompt_builder or build_transcript_insight_prompt
    segments = await session_store.get_segments(uid, session_id)
    if not segments:
        return None
    previous = await insight_store.get(uid, session_id) or {}
    analyzed_upto = previous.get("analyzed_segments", 0)
    tail = segments[analyzed_upto:]
    if not tail:
        return None
    messages = builder(tail)
    try:
        text = await llm_chat(messages)
    except Exception as exc:
        import logging

        logging.getLogger("omi-apps.analysis").warning(
            "analysis failed uid=%s session=%s err=%s", uid, session_id, type(exc).__name__
        )
        return None
    await insight_store.save(
        uid,
        session_id,
        {
            "text": text,
            "analyzed_segments": analyzed_upto + len(tail),
            "created_at_ts": time.time(),
            "session_id": session_id,
        },
    )
    return text
