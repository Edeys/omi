import time

import pytest

from app.store.sessions import (
    SILENCE_RESET_SECONDS,
    BufferState,
    SessionStore,
    segment_key,
)


@pytest.fixture
def memory_store() -> SessionStore:
    return SessionStore(redis_client=None)


@pytest.mark.asyncio
async def test_append_and_dedupe(memory_store: SessionStore) -> None:
    segs = [{"speaker": "user", "text": "hello", "start": 0.0, "end": 1.0}]
    fresh = await memory_store.append_segments("u", "s", segs)
    assert len(fresh) == 1
    fresh2 = await memory_store.append_segments("u", "s", segs)
    assert fresh2 == []
    buffered = await memory_store.get_segments("u", "s")
    assert len(buffered) == 1


@pytest.mark.asyncio
async def test_silence_resets_buffer(memory_store: SessionStore) -> None:
    segs_old = [{"speaker": "user", "text": "old talk", "start": 0.0, "end": 2.0}]
    await memory_store.append_segments("u", "sil", [seg for seg in segs_old])
    k = f"omi-apps:session:u:sil"
    from app.store import sessions as sessions_mod

    state = sessions_mod._memory_buffers[k]
    state.last_activity = time.time() - (SILENCE_RESET_SECONDS + 10)
    new_seg = {"speaker": "user", "text": "fresh topic after silence", "start": 100.0, "end": 102.0}
    fresh = await memory_store.append_segments("u", "sil", [new_seg])
    assert fresh == [new_seg]
    buffered = await memory_store.get_segments("u", "sil")
    assert buffered == [new_seg]


@pytest.mark.asyncio
async def test_clear_removes_session(memory_store: SessionStore) -> None:
    await memory_store.append_segments("u", "c", [{"speaker": "user", "text": "abc"}])
    await memory_store.clear("u", "c")
    assert await memory_store.get_segments("u", "c") == []


def test_segment_key_stable_and_distinct() -> None:
    a = {"speaker": "user", "text": "hi", "start": 0.0, "end": 1.0}
    b = {"start": 0.0, "end": 1.0, "text": "hi", "speaker": "user"}
    c = {"speaker": "user", "text": "hi!", "start": 0.0, "end": 1.0}
    assert segment_key(a) == segment_key(b)
    assert segment_key(a) != segment_key(c)
