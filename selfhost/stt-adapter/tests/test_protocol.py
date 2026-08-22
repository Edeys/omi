"""Protocol contract tests for the Deepgram-subset STT adapter.

Pinned wire contract sources:
- .superpowers/sdd/2026-08-21-omi-selfhost-backend/task-1-report.md lines 61-66
  (LiveOptions sample_rate=16000 encoding=linear16 channels=1, binary PCM16 LE mono,
  server events consumed: Results/Metadata/Error; WS path derived by deepgram-sdk 4.8.1
  from DEEPGRAM_SELF_HOSTED_URL is {base}/v1/listen).
- backend/utils/stt/streaming.py:662-696 (Results consumption),
  streaming.py:841-856 (client Start options), streaming.py:820-838 (Metadata handling).

Note on the brief's handshake assert (`first["type"] in ("Ready", "Results")`): the pinned
Deepgram protocol has no "Ready" message type — an unknown type would surface in the
backend as an Unhandled event and be logged as an error (streaming.py:832-833). The Start
ack therefore uses the SDK-native "Metadata" message, which the backend already handles.
"""

import json
import wave

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main
import protocol

from conftest import ScriptedRecognizer


def _send_start(ws, **overrides):
    payload = {
        "type": "Start",
        "encoding": "linear16",
        "sample_rate": 16000,
        "channels": 1,
        "interim_results": False,
        "language": "vi",
        "model": "nova-3",
    }
    payload.update(overrides)
    ws.send_text(json.dumps(payload))
    return json.loads(ws.receive_text())


def _silence_pcm(ms: int) -> bytes:
    return b"\x00\x00" * (16 * ms)


def _expect_disconnect(ws):
    with pytest.raises(WebSocketDisconnect):
        ws.receive_text()


def test_start_ack_then_closestream_flushes_and_closes():
    client = TestClient(main.app)
    with client.websocket_connect("/v1/stream") as ws:
        ack = _send_start(ws)
        assert ack["type"] == "Metadata"
        ws.send_bytes(_silence_pcm(100))
        ws.send_text(json.dumps({"type": "CloseStream"}))
        last = json.loads(ws.receive_text())
        assert last["type"] == "Results"
        assert last["is_final"] is True
        assert last["channel"]["alternatives"][0]["transcript"] == "xin chào thế giới"
        _expect_disconnect(ws)


def test_binary_pcm_yields_deepgram_results_envelope():
    main.set_recognizer_factory(
        lambda: ScriptedRecognizer(
            segments=[{"text": "xin chào", "is_final": True, "start": 0.0, "duration": 0.6}]
        )
    )
    client = TestClient(main.app)
    with client.websocket_connect("/v1/stream") as ws:
        ack = _send_start(ws)
        assert ack["type"] == "Metadata"
        ws.send_bytes(_silence_pcm(600))
        msg = json.loads(ws.receive_text())
    assert msg["type"] == "Results"
    assert msg["channel_index"] == [0, 1]
    assert msg["is_final"] is True
    assert isinstance(msg["start"], float)
    assert isinstance(msg["duration"], float)
    alt = msg["channel"]["alternatives"][0]
    assert alt["transcript"] == "xin chào"
    assert alt["language"] == "vi"
    words = alt["words"]
    assert [w["word"] for w in words] == ["xin", "chào"]
    for w in words:
        assert w["speaker"] == 0
        assert w["punctuated_word"]
        assert w["confidence"] >= 0.0
        assert w["end"] > w["start"] or w["word"] != "chào"
    assert words[0]["start"] == pytest.approx(0.0)


def test_finalize_flushes_pending_transcript():
    main.set_recognizer_factory(lambda: ScriptedRecognizer(flushed=[
        {"text": "một hai ba", "is_final": True, "start": 0.2, "duration": 0.9}
    ]))
    client = TestClient(main.app)
    with client.websocket_connect("/v1/stream") as ws:
        _send_start(ws)
        ws.send_bytes(_silence_pcm(200))
        ws.send_text(json.dumps({"type": "Finalize"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "Results"
        assert msg["from_finalize"] is True
        assert msg["channel"]["alternatives"][0]["transcript"] == "một hai ba"


@pytest.mark.parametrize(
    "override",
    [{"sample_rate": 44100}, {"encoding": "mulaw"}, {"channels": 2}],
)
def test_start_rejects_unsupported_config(override):
    client = TestClient(main.app)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(json.dumps({"type": "Start", **override}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "Error"
        _expect_disconnect(ws)


def test_binary_before_start_is_rejected():
    client = TestClient(main.app)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_bytes(_silence_pcm(10))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "Error"
        _expect_disconnect(ws)


def test_malformed_json_closes_with_error():
    client = TestClient(main.app)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text("{not json")
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "Error"
        _expect_disconnect(ws)


def test_keepalive_between_chunks_keeps_stream_alive():
    main.set_recognizer_factory(
        lambda: ScriptedRecognizer(
            segments=[{"text": "ok", "is_final": True, "start": 0.0, "duration": 0.5}]
        )
    )
    client = TestClient(main.app)
    with client.websocket_connect("/v1/stream") as ws:
        _send_start(ws)
        ws.send_text(json.dumps({"type": "KeepAlive"}))
        ws.send_bytes(_silence_pcm(500))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "Results"
        assert msg["channel"]["alternatives"][0]["transcript"] == "ok"


def test_v1_listen_alias_matches_sdk_derived_path():
    # deepgram-sdk 4.8.1 connects to {DEEPGRAM_SELF_HOSTED_URL}/v1/listen
    # (task-1-report.md line 66).
    client = TestClient(main.app)
    with client.websocket_connect("/v1/listen") as ws:
        ack = _send_start(ws)
        assert ack["type"] == "Metadata"
        ws.send_bytes(_silence_pcm(100))
        ws.send_text(json.dumps({"type": "CloseStream"}))
        last = json.loads(ws.receive_text())
        assert last["type"] == "Results"


# ---------------------------------------------------------------------------
# protocol.py unit tests
# ---------------------------------------------------------------------------


def test_validate_start_accepts_pinned_live_options():
    # Exact LiveOptions set sent by backend/utils/stt/streaming.py:841-856.
    payload = {
        "type": "Start",
        "punctuate": True,
        "no_delay": True,
        "endpointing": 300,
        "language": "vi",
        "interim_results": False,
        "smart_format": True,
        "profanity_filter": False,
        "diarize": True,
        "filler_words": False,
        "channels": 1,
        "multichannel": False,
        "model": "nova-3",
        "sample_rate": 16000,
        "encoding": "linear16",
    }
    cfg = protocol.validate_start(payload)
    assert cfg.sample_rate == 16000
    assert cfg.encoding == "linear16"
    assert cfg.channels == 1


@pytest.mark.parametrize("override", [{"sample_rate": "16k"}, {"channels": "mono"}])
def test_validate_start_rejects_wrong_typed_options(override):
    # Regression: wrong-typed int options must surface as a ProtocolError
    # (Deepgram Error frame + clean close), not an unhandled ValueError.
    with pytest.raises(protocol.ProtocolError) as excinfo:
        protocol.validate_start({"type": "Start", **override})
    key = next(iter(override))
    assert key in str(excinfo.value.message)


def test_parse_client_message_rejects_non_json_and_missing_type():
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_client_message("not json")
    with pytest.raises(protocol.ProtocolError):
        protocol.parse_client_message(json.dumps({"encoding": "linear16"}))


def test_encode_results_words_split_timing():
    text = "xin chào thế giới"
    raw = json.loads(
        protocol.encode_results(text=text, start_seconds=1.0, duration_seconds=2.0)
    )
    alt = raw["channel"]["alternatives"][0]
    assert len(alt["words"]) == 4
    assert raw["start"] == pytest.approx(1.0)
    assert raw["duration"] == pytest.approx(2.0)
    last = alt["words"][-1]
    assert last["end"] == pytest.approx(3.0)


def test_chunk_duration_math():
    # 19200 bytes of PCM16 mono @16kHz = 0.6s
    assert protocol.chunk_duration_seconds(19200) == pytest.approx(0.6)


def test_health_endpoint_reports_ok():
    client = TestClient(main.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_sample_fixture_wav_is_pcm16_16k_mono(sample_vi_wav_path):
    with wave.open(str(sample_vi_wav_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
