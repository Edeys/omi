import asyncio
import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger("omi-apps.sessions")

SILENCE_RESET_SECONDS = 120
SESSION_TTL_SECONDS = 3600
MIN_WORDS_AFTER_SILENCE = 5

_memory_buffers: dict[str, "BufferState"] = {}
_lock = asyncio.Lock()


def _key(uid: str, session_id: str) -> str:
    return f"omi-apps:session:{uid}:{session_id}"


def segment_key(segment: dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "speaker": segment.get("speaker"),
            "text": segment.get("text"),
            "start": segment.get("start"),
            "end": segment.get("end"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class BufferState:
    def __init__(self) -> None:
        self.segments: list[dict[str, Any]] = []
        self.seen: set[str] = set()
        self.last_activity: float = time.time()


class SessionStore:
    """Transcript session buffers with dedupe, silence reset and TTL cleanup.

    Uses Redis when reachable; falls back to in-process memory so tests and
    degraded operation keep working without a live Redis.
    """

    def __init__(self, redis_client: Any = None) -> None:
        self._redis = redis_client

    async def append_segments(self, uid: str, session_id: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not segments:
            return []
        async with _lock:
            state = await self._load(uid, session_id)
            now = time.time()
            fresh: list[dict[str, Any]] = []
            if now - state.last_activity > SILENCE_RESET_SECONDS:
                word_count = sum(len(s.get("text", "").split()) for s in state.segments)
                state.segments = [] if not state.segments else state.segments
                if word_count or state.segments:
                    state.segments = []
                    state.seen = set()
            for seg in segments:
                key = segment_key(seg)
                if key in state.seen:
                    continue
                state.seen.add(key)
                state.segments.append(seg)
                fresh.append(seg)
            state.last_activity = now
            await self._save(uid, session_id, state)
            return fresh

    async def get_segments(self, uid: str, session_id: str) -> list[dict[str, Any]]:
        async with _lock:
            state = await self._load(uid, session_id)
            return list(state.segments)

    async def clear(self, uid: str, session_id: str) -> None:
        async with _lock:
            _memory_buffers.pop(_key(uid, session_id), None)
            if self._redis is not None:
                try:
                    await self._redis.delete(_key(uid, session_id))
                except Exception as exc:
                    logger.warning("redis delete failed, using memory only: %s", type(exc).__name__)

    async def _load(self, uid: str, session_id: str) -> BufferState:
        k = _key(uid, session_id)
        if self._redis is not None:
            try:
                raw = await self._redis.get(k)
                if raw:
                    data = json.loads(raw)
                    state = BufferState()
                    state.segments = data.get("segments", [])
                    state.seen = set(data.get("seen", []))
                    state.last_activity = data.get("last_activity", time.time())
                    return state
            except Exception as exc:
                logger.warning("redis read failed, falling back to memory: %s", type(exc).__name__)
        return _memory_buffers.setdefault(k, BufferState())

    async def _save(self, uid: str, session_id: str, state: BufferState) -> None:
        k = _key(uid, session_id)
        cutoff = time.time() - SESSION_TTL_SECONDS
        for stale in [sk for sk, sv in _memory_buffers.items() if sv.last_activity < cutoff]:
            _memory_buffers.pop(stale, None)
        if self._redis is not None:
            try:
                payload = json.dumps(
                    {
                        "segments": state.segments,
                        "seen": list(state.seen),
                        "last_activity": state.last_activity,
                    }
                )
                await self._redis.set(k, payload, ex=SESSION_TTL_SECONDS)
                return
            except Exception as exc:
                logger.warning("redis write failed, keeping memory copy: %s", type(exc).__name__)
        _memory_buffers[k] = state


store = SessionStore()
