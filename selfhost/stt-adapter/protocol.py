"""Deepgram self-hosted streaming subset spoken by this adapter.

Pinned contract sources:
- .superpowers/sdd/2026-08-21-omi-selfhost-backend/task-1-report.md lines 61-66:
  deepgram-sdk 4.8.1 derives the WS path ``{DEEPGRAM_SELF_HOSTED_URL}/v1/listen``
  from the configured HTTP base; the client opens with a JSON ``Start`` carrying
  LiveOptions (sample_rate=16000, encoding='linear16', channels=1) and streams
  binary PCM16 little-endian mono frames.
- backend/utils/stt/streaming.py:841-856 — exact LiveOptions the backend sends.
- backend/utils/stt/streaming.py:662-696 — how Results are consumed:
  channel.alternatives[0].transcript plus words[].speaker/start/end/punctuated_word.
- backend/utils/stt/streaming.py:820-838 — Metadata is an SDK-native event the
  backend already handles, hence it doubles as the Start acknowledgement here.
"""

import json
from dataclasses import dataclass

SAMPLE_RATE = 16000
ENCODING = "linear16"
CHANNELS = 1
BYTES_PER_SAMPLE = 2

# Placeholder alternative confidence: greedy decoding exposes no calibrated
# score and the backend never reads alternatives[].confidence (streaming.py:662-696).
_PLACEHOLDER_CONFIDENCE = 1.0


class ProtocolError(Exception):
    def __init__(self, message: str, close_code: int = 1008):
        super().__init__(message)
        self.message = message
        self.close_code = close_code


@dataclass
class StartConfig:
    sample_rate: int
    encoding: str
    channels: int
    interim_results: bool
    language: str
    model: str


def parse_client_message(raw: str) -> dict:
    """Parse one client text frame into {'type': <str>, 'payload': <dict>}."""
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        raise ProtocolError("Message is not valid JSON")
    if not isinstance(doc, dict) or not isinstance(doc.get("type"), str) or not doc["type"]:
        raise ProtocolError('Message must be a JSON object with a "type" field')
    payload = {k: v for k, v in doc.items() if k != "type"}
    return {"type": doc["type"], "payload": payload}


def validate_start(payload: dict) -> StartConfig:
    """Validate the pinned LiveOptions subset; ignore options we cannot honor.

    The backend always sends the full LiveOptions block (punctuate, smart_format,
    diarize, endpointing, ...) — unknown/unhonored keys are accepted silently;
    anything that would corrupt the audio contract is rejected.
    """
    encoding = payload.get("encoding", ENCODING)
    if encoding != ENCODING:
        raise ProtocolError(
            f"Unsupported encoding {encoding!r}: this endpoint accepts '{ENCODING}' only"
        )
    sample_rate = int(payload.get("sample_rate", SAMPLE_RATE))
    if sample_rate != SAMPLE_RATE:
        raise ProtocolError(
            f"Unsupported sample_rate {sample_rate}: the loaded model requires {SAMPLE_RATE}Hz"
        )
    channels = int(payload.get("channels", CHANNELS))
    if channels != CHANNELS:
        raise ProtocolError(
            f"Unsupported channels {channels}: this endpoint accepts mono ({CHANNELS}) only"
        )
    return StartConfig(
        sample_rate=sample_rate,
        encoding=encoding,
        channels=channels,
        interim_results=bool(payload.get("interim_results", False)),
        language=str(payload.get("language", "vi")),
        model=str(payload.get("model", "")),
    )


def chunk_duration_seconds(num_bytes: int) -> float:
    return num_bytes / (BYTES_PER_SAMPLE * SAMPLE_RATE)


def _words_for(text: str, start: float, duration: float) -> list[dict]:
    """Split a transcript into Deepgram word entries, spreading duration evenly."""
    words = text.split()
    if not words:
        return []
    step = duration / len(words)
    entries = []
    for i, word in enumerate(words):
        entries.append(
            {
                "word": word,
                "start": round(start + i * step, 3),
                "end": round(start + (i + 1) * step, 3),
                "confidence": _PLACEHOLDER_CONFIDENCE,
                "speaker": 0,
                # Diarization is not modeled upstream (single SPEAKER_0 tolerated
                # per task-1-report.md line 66); punctuation is passed through.
                "punctuated_word": word,
            }
        )
    return entries


def encode_results(
    text: str,
    *,
    start_seconds: float = 0.0,
    duration_seconds: float = 0.0,
    language: str = "vi",
    is_final: bool = True,
    from_finalize: bool = False,
) -> str:
    """Build one Deepgram-shaped Results message (the shape streaming.py consumes)."""
    return json.dumps(
        {
            "type": "Results",
            "channel_index": [0, 1],
            "start": round(float(start_seconds), 3),
            "duration": round(float(duration_seconds), 3),
            "is_final": bool(is_final),
            "speech_final": bool(is_final),
            "from_finalize": bool(from_finalize),
            "channel": {
                "alternatives": [
                    {
                        "transcript": text,
                        "confidence": _PLACEHOLDER_CONFIDENCE,
                        "words": _words_for(text, float(start_seconds), float(duration_seconds)),
                        "language": language,
                    }
                ],
                "language": language,
            },
            "metadata": {
                "transaction_key": "async",
                "request_id": "",
                "model_info": {"name": "sherpa-onnx-streaming-zipformer-vi", "architecture": "zipformer"},
                "extra": None,
            },
        },
        ensure_ascii=False,
    )


def encode_metadata(request_id: str, model_name: str) -> str:
    return json.dumps(
        {
            "type": "Metadata",
            "transaction_key": "async",
            "request_id": request_id,
            "model_info": {"name": model_name, "architecture": "zipformer"},
            "extra": None,
        }
    )


def encode_error(message: str, close_code: int = 1008) -> str:
    return json.dumps({"type": "Error", "description": message, "code": close_code})
