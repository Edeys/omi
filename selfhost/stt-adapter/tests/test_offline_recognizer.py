"""Unit tests for the VAD-segmented offline recognizer (STT_ENGINE=offline).

sherpa_onnx is faked at the sys.modules level so the suite runs hermetically
without the native wheel - same rule as the protocol tests. The fakes pin the
exact sherpa-onnx surface ViOfflineRecognizer/_OfflineEngine touch:
  VadModelConfig().silero_vad.{model,threshold,min_speech_duration,
  min_silence_duration}, config.sample_rate, Vad(config, buffer_size_in_seconds),
  vad.{accept_waveform,empty,front,pop,flush}, OfflineRecognizer.from_transducer,
  recognizer.create_stream().accept_waveform(sr, samples), decode_stream,
  stream.result.text.
"""

import sys
import types

import pytest

import recognizer as recognizer_mod

SR = 16000


class _FakeSilero:
    model = ""
    threshold = 0.5
    min_speech_duration = 0.25
    min_silence_duration = 0.45


class _FakeVadModelConfig:
    def __init__(self):
        self.silero_vad = _FakeSilero()
        self.sample_rate = SR


class _FakeSegment:
    def __init__(self, start: int, samples):
        self.start = start
        self.samples = samples


class _FakeVad:
    instances: list = []

    def __init__(self, config, buffer_size_in_seconds=120.0):
        self.config = config
        self.buffer_size_in_seconds = buffer_size_in_seconds
        self.scripted: list[_FakeSegment] = []
        self.pending: list[_FakeSegment] = []
        self.fed_samples = 0
        self.flushed = False
        type(self).instances.append(self)

    def accept_waveform(self, samples):
        self.fed_samples += len(samples)
        while self.scripted:
            self.pending.append(self.scripted.pop(0))

    def empty(self) -> bool:
        return not self.pending

    @property
    def front(self):
        return self.pending[0] if self.pending else None

    def pop(self):
        self.pending.pop(0)

    def flush(self):
        self.flushed = True


class _FakeStream:
    def __init__(self, texts: dict, key: str):
        self.result = types.SimpleNamespace(text=texts.get(key, ""))

    def accept_waveform(self, sample_rate, samples):
        pass


class _FakeOfflineRecognizer:
    def __init__(self, kwargs: dict, texts: dict):
        self.kwargs = kwargs
        self._texts = texts

    def create_stream(self):
        return _FakeStream(self._texts, "seg")

    def decode_stream(self, stream):
        pass


@pytest.fixture
def fake_sherpa(monkeypatch, tmp_path):
    """Fake sherpa_onnx module + fake model dir; no downloads, no native wheel."""
    # Pre-place silero_vad.onnx so the engine skips the download.
    vad_model = tmp_path / "silero_vad.onnx"
    vad_model.write_bytes(b"fake-vad")
    monkeypatch.setenv("STT_MODELS_DIR", str(tmp_path))
    monkeypatch.delenv("STT_VAD_THRESHOLD", raising=False)

    # Fake model dir satisfying _pick_component globs.
    model_dir = tmp_path / "fake-model"
    model_dir.mkdir()
    for name in ("tokens.txt", "encoder.int8.onnx", "decoder.onnx", "joiner.int8.onnx"):
        (model_dir / name).write_text("fake")

    created: dict = {}

    class FakeSherpa(types.ModuleType):
        class OfflineRecognizer:
            @staticmethod
            def from_transducer(**kwargs):
                created["recognizer_kwargs"] = kwargs
                return _FakeOfflineRecognizer(kwargs, created.setdefault("texts", {}))

        VadModelConfig = _FakeVadModelConfig
        Vad = _FakeVad

    fake = types.ModuleType("sherpa_onnx")
    fake.OfflineRecognizer = FakeSherpa.OfflineRecognizer
    fake.VadModelConfig = _FakeVadModelConfig
    fake.VoiceActivityDetector = _FakeVad
    monkeypatch.setitem(sys.modules, "sherpa_onnx", fake)

    yield {"created": created, "vads": _FakeVad.instances, "model_dir": str(model_dir)}

    _FakeVad.instances.clear()


def test_offline_recognizer_transcribes_vad_segments(fake_sherpa, monkeypatch):
    """Speech segments closed by the VAD become final Results with timing."""
    monkeypatch.setattr(recognizer_mod, "pcm16_to_float32", lambda pcm: [0.0] * (len(pcm) // 2))
    engine = object.__new__(recognizer_mod._OfflineEngine)
    engine.recognizer = _FakeOfflineRecognizer({}, {"seg": "xin chào việt nam"})
    engine.vad_config = _FakeVadModelConfig()

    rec = recognizer_mod.ViOfflineRecognizer(engine)
    assert len(_FakeVad.instances) >= 1
    vad = _FakeVad.instances[-1]
    # Script one utterance: starts at 1 s of audio, 2 s long.
    vad.scripted.append(_FakeSegment(start=SR * 1, samples=[0.0] * (SR * 2)))

    out = rec.transcribe_chunk(b"\x00\x00" * (SR * 3))  # feed 3 s of audio
    assert len(out) == 1
    seg = out[0]
    assert seg["text"] == "xin chào việt nam"
    assert seg["is_final"] is True
    assert seg["start"] == 1.0
    assert abs(seg["duration"] - 2.0) < 0.01


def test_offline_flush_marks_flushed_and_returns_empty_without_segments(fake_sherpa, monkeypatch):
    monkeypatch.setattr(recognizer_mod, "pcm16_to_float32", lambda pcm: [0.0] * (len(pcm) // 2))
    engine = object.__new__(recognizer_mod._OfflineEngine)
    engine.recognizer = _FakeOfflineRecognizer({}, {})
    engine.vad_config = _FakeVadModelConfig()

    rec = recognizer_mod.ViOfflineRecognizer(engine)
    vad = _FakeVad.instances[-1]

    assert rec.transcribe_chunk(b"\x00\x00" * SR) == []
    out_flush = rec.flush()
    assert vad.flushed is True
    assert out_flush == []


def test_offline_engine_reads_env_threshold_and_threads(fake_sherpa, monkeypatch):
    monkeypatch.setenv("STT_VAD_THRESHOLD", "0.7")
    engine = recognizer_mod._OfflineEngine(
        model_dir=fake_sherpa["model_dir"], num_threads=3
    )
    assert engine.vad_config.silero_vad.threshold == 0.7
    kwargs = fake_sherpa["created"]["recognizer_kwargs"]
    assert kwargs["num_threads"] == 3
    assert kwargs["encoder"].endswith("encoder.int8.onnx")


def test_offline_flush_emits_buffered_tail_when_no_vad_endpoint(fake_sherpa, monkeypatch):
    """Continuous speech without a VAD endpoint is flushed as one final segment."""
    captured = {}

    def fake_decode(self, samples_arg):
        captured["n"] = len(samples_arg)
        return "xin chào"

    monkeypatch.setattr(recognizer_mod, "pcm16_to_float32", lambda pcm: [0.0] * (len(pcm) // 2))
    monkeypatch.setattr(recognizer_mod.ViOfflineRecognizer, "_decode_samples", fake_decode)
    engine = object.__new__(recognizer_mod._OfflineEngine)
    engine.recognizer = types.SimpleNamespace(
        create_stream=lambda: types.SimpleNamespace(
            accept_waveform=lambda sr, s: None,
            result=types.SimpleNamespace(text=""),
            **{},
        ),
        decode_stream=lambda stream: setattr(stream.result, "text", "xin chào"),
    )
    engine.vad_config = _FakeVadModelConfig()

    rec = recognizer_mod.ViOfflineRecognizer(engine)
    vad = _FakeVad.instances[-1]
    # No scripted VAD segment -> nothing emitted during streaming.
    assert rec.transcribe_chunk(b"\x00\x00" * (SR * 3)) == []
    out = rec.flush()
    assert vad.flushed is True
    assert len(out) == 1
    assert out[0]["text"] == "xin chào"
    assert out[0]["is_final"] is True
    # The flushed tail must contain the full 3 s of buffered audio.
    assert captured["n"] == SR * 3

def test_interim_text_is_always_empty_for_offline(fake_sherpa):
    engine = object.__new__(recognizer_mod._OfflineEngine)
    engine.recognizer = None
    engine.vad_config = _FakeVadModelConfig()
    rec = recognizer_mod.ViOfflineRecognizer(engine)
    assert rec.interim_text() == ""
