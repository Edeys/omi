import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_manifest_endpoint() -> None:
    res = client.get("/.well-known/omi-tools.json")
    assert res.status_code == 200
    assert "chat_tools" in res.json()


def test_transcript_requires_uid() -> None:
    res = client.post("/webhook/transcript", json={"segments": [{"speaker": "user", "text": "xin chao"}]})
    assert res.status_code == 422


def test_transcript_accepts_segments() -> None:
    res = client.post(
        "/webhook/transcript?uid=u1&session_id=s1",
        json={"segments": [{"speaker": "user", "text": "xin chao", "start": 0.0, "end": 1.0}]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["received"] == 1
    assert data["new"] == 1


def test_transcript_rejects_non_list_segments() -> None:
    res = client.post("/webhook/transcript?uid=u1&session_id=s2", json={"segments": "oops"})
    assert res.status_code == 422


def test_memory_requires_uid() -> None:
    res = client.post("/webhook/memory", json={"id": "m1"})
    assert res.status_code == 422


def test_memory_accepts_valid_object() -> None:
    res = client.post("/webhook/memory?uid=u1", json={"id": "m1", "transcript": "noi chuyen", "summary": "tom tat"})
    assert res.status_code == 200


def test_memory_rejects_empty_object() -> None:
    res = client.post("/webhook/memory?uid=u1", json={})
    assert res.status_code == 422


def test_audio_requires_uid() -> None:
    res = client.post("/webhook/audio", content=b"\x00\x01")
    assert res.status_code == 422


def test_audio_accepts_pcm_bytes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "audio_store_dir", str(tmp_path))
    payload = b"\x00\x00" * 1600
    res = client.post("/webhook/audio?uid=u1&sample_rate=16000", content=payload)
    assert res.status_code == 200
    assert res.json()["bytes"] == len(payload)
    assert res.json()["sample_rate"] == 16000


def test_audio_rejects_bad_sample_rate() -> None:
    res = client.post("/webhook/audio?uid=u1&sample_rate=abc", content=b"\x00\x00")
    assert res.status_code == 422


def test_day_summary_parses_summary_json() -> None:
    res = client.post(
        "/webhook/day_summary?uid=u1",
        json={"summary_json": {"headline": "Hom nay lam viec"}, "created_at": "2026-08-23T22:00:00+00:00"},
    )
    assert res.status_code == 200


def test_day_summary_rejects_missing_summary() -> None:
    res = client.post("/webhook/day_summary?uid=u1", json={"created_at": "2026-08-23T22:00:00+00:00"})
    assert res.status_code == 422
