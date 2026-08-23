import time

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.processing.transcript_analyzer import (
    insight_store,
    record_for_analysis,
    run_analysis,
    unanalyzed_word_count,
)
from app.store.sessions import store as session_store

client = TestClient(app)


def _segs(texts: list[str]) -> list[dict]:
    return [{"speaker": "user", "text": t, "start": 0.0, "end": 1.0} for t in texts]


def test_unanalyzed_word_count() -> None:
    segs = _segs(["mot hai", "ba bon nam"])
    assert unanalyzed_word_count(segs, 0) == 5
    assert unanalyzed_word_count(segs, 1) == 3
    assert unanalyzed_word_count(segs, 2) == 0


@pytest.mark.asyncio
async def test_below_threshold_not_scheduled() -> None:
    await insight_store.save("u_t1", "s1", {"analyzed_segments": 0})
    await session_store.clear("u_t1", "s1")
    await session_store.append_segments("u_t1", "s1", _segs(["chi vai tu"]))
    ok = await record_for_analysis("u_t1", "s1", min_new_words=40, interval_seconds=120)
    assert ok is False


@pytest.mark.asyncio
async def test_above_threshold_and_interval_passes() -> None:
    await session_store.clear("u_t2", "s2")
    await insight_store.save("u_t2", "s2", {})
    words = " ".join(str(i) for i in range(50))
    await session_store.append_segments("u_t2", "s2", _segs([words]))
    ok = await record_for_analysis("u_t2", "s2", min_new_words=40, interval_seconds=120, now=time.time())
    assert ok is True


@pytest.mark.asyncio
async def test_interval_throttle_blocks_rerun() -> None:
    await session_store.clear("u_t3", "s3")
    await insight_store.save(
        "u_t3", "s3", {"analyzed_segments": 0, "created_at_ts": time.time()}
    )
    words = " ".join(f"tu{i}" for i in range(50))
    await session_store.append_segments("u_t3", "s3", _segs([words]))
    ok = await record_for_analysis("u_t3", "s3", min_new_words=40, interval_seconds=300, now=time.time())
    assert ok is False


@pytest.mark.asyncio
async def test_run_analysis_persists_insight() -> None:
    await session_store.clear("u_t4", "s4")
    await insight_store.save("u_t4", "s4", {})

    async def fake_llm(messages):
        return "Nhan dinh gia lap"

    texts = [" ".join(f"loi{i}" for i in range(30))]
    await session_store.append_segments("u_t4", "s4", _segs(texts))
    out = await run_analysis("u_t4", "s4", fake_llm)
    assert out == "Nhan dinh gia lap"
    saved = await insight_store.get("u_t4", "s4")
    assert saved["analyzed_segments"] == 1
    assert saved["text"] == "Nhan dinh gia lap"


@pytest.mark.asyncio
async def test_run_analysis_skips_when_nothing_new() -> None:
    called = {"n": 0}

    async def fake_llm(messages):
        called["n"] += 1
        return "x"

    out = await run_analysis("u_empty", "s_none", fake_llm)
    assert out is None
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_run_analysis_llm_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    await session_store.clear("u_t5", "s5")
    await insight_store.save("u_t5", "s5", {})

    async def bad_llm(messages):
        raise RuntimeError("boom")

    await session_store.append_segments("u_t5", "s5", _segs(["noi gi do dai dai hon"]))
    out = await run_analysis("u_t5", "s5", bad_llm)
    assert out is None
    saved = await insight_store.get("u_t5", "s5")
    assert not saved or saved.get("analyzed_segments") in (None, 0)


def test_webhook_response_shape_with_small_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "analysis_min_new_words", 2)
    monkeypatch.setattr(settings, "analysis_interval_seconds", 0)

    async def noop_job(uid: str, session_id: str) -> None:
        return None

    import app.webhooks.transcript as transcript_module

    original = transcript_module._run_analysis_job
    transcript_module._run_analysis_job = noop_job
    try:
        res = client.post(
            "/webhook/transcript?uid=u_web&session_id=s_web",
            json={"segments": [{"speaker": "user", "text": "du nhieu tu de phan tich ngay"}]},
        )
        data = res.json()
        assert res.status_code == 200
        assert data["analysis_scheduled"] is True
    finally:
        transcript_module._run_analysis_job = original


def test_insight_endpoint_empty_then_ok() -> None:
    res = client.get("/webhook/transcript/insight?uid=nobody&session_id=nothing")
    assert res.status_code == 200
    assert res.json()["status"] in ("empty", "ok")
