import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402


class ScriptedRecognizer:
    """Stub ViRecognizer: replays scripted segments, records fed PCM."""

    def __init__(self, segments=None, flushed=None):
        self.segments = list(segments or [])
        self.flushed = list(flushed or [])
        self.fed_chunks = []

    def transcribe_chunk(self, pcm: bytes):
        if self.segments:
            return [self.segments.pop(0)]
        return []

    def flush(self):
        out = self.flushed
        self.flushed = []
        return out


def _default_stub():
    return ScriptedRecognizer(
        flushed=[{"text": "xin chào thế giới", "is_final": True, "start": 0.0, "duration": 1.2}]
    )


@pytest.fixture(autouse=True)
def stub_recognizer():
    main.set_recognizer_factory(_default_stub)
    yield
    main.set_recognizer_factory(None)


FIXTURE_WAV = Path(__file__).resolve().parent / "fixtures" / "sample-vi.wav"


def _generate_wav(path: Path) -> None:
    import math
    import struct

    rate = 16000
    seconds = 0.6
    frames = bytearray()
    for i in range(int(rate * seconds)):
        envelope = min(1.0, i / 800.0, (rate * seconds - i) / 800.0)
        v = int(12000 * envelope * math.sin(2 * math.pi * 220 * i / rate))
        frames += struct.pack("<h", v)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(bytes(frames))


@pytest.fixture
def sample_vi_wav_path() -> Path:
    """Committed deterministic PCM16 16kHz mono fixture (format validity only — NOT speech evidence).

    Regenerated on the fly if missing so the suite stays self-contained.
    """
    if not FIXTURE_WAV.is_file():
        FIXTURE_WAV.parent.mkdir(parents=True, exist_ok=True)
        _generate_wav(FIXTURE_WAV)
    return FIXTURE_WAV
