"""sherpa-onnx Vietnamese streaming recognizer behind the ViRecognizer interface.

Model: zipformer-vi-30M-int8 (pinned tarball, downloaded once into the
``stt_models`` compose volume). Heavy imports (numpy, sherpa_onnx) are deferred
to first use so protocol-level tests run without them.
"""

import logging
import os
import shutil
import tarfile
import threading
import urllib.request
from pathlib import Path

logger = logging.getLogger("stt_adapter.recognizer")

DEFAULT_MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-streaming-zipformer-ar_en_id_ja_ru_th_vi_zh-2025-02-10.tar.bz2"
)
MODEL_DIR_NAME = "sherpa-onnx-streaming-zipformer-ar_en_id_ja_ru_th_vi_zh-2025-02-10"
# NOTE on the originally pinned asset: task-6's brief pointed at
# sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2, but its encoder.int8.onnx
# carries metadata `comment = non-streaming zipformer2` (inputs x/x_lens, no
# encoder_dims), so sherpa-onnx OnlineRecognizer cannot load it Ã¢â‚¬â€ verified by
# crash ('encoder_dims' does not exist in the metadata) and ONNX metadata
# inspection. The streaming multilingual vi-capable zipformer from the same
# release tag is the streaming default; the offline VietASR model (70k hours,
# WER ~10% avg, Interspeech 2025) is served through the VAD-segmented offline path
# below (STT_ENGINE=offline) Ã¢â‚¬â€ "simulated streaming" per the sherpa-onnx
# vad-microphone-simulated-streaming-asr recipe.
OFFLINE_MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-zipformer-vi-int8-2025-04-20.tar.bz2"
)
OFFLINE_MODEL_DIR_NAME = "sherpa-onnx-zipformer-vi-int8-2025-04-20"
SILERO_VAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
)
DEFAULT_MODELS_ROOT = "/models"
MODEL_DOWNLOAD_TIMEOUT_S = 30  # per-socket-op (connect/read); slow-but-active downloads are fine
SAMPLE_RATE = 16000


def _models_root() -> Path:
    return Path(os.getenv("STT_MODELS_DIR", DEFAULT_MODELS_ROOT))


def _resolve_model_dir(path: Path) -> Path:
    """Locate the dir holding tokens.txt, descending into tar-style wrapper dirs."""
    if (path / "tokens.txt").is_file():
        return path
    for child in sorted(p for p in path.iterdir() if p.is_dir()):
        try:
            return _resolve_model_dir(child)
        except FileNotFoundError:
            continue
    raise FileNotFoundError(f"no tokens.txt found under {path}")


def _safe_extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    base = dest.resolve()
    with tarfile.open(archive, "r:bz2") as tar:
        for member in tar.getmembers():
            target = (base / member.name).resolve()
            if not target.is_relative_to(base):
                raise ValueError(f"refusing unsafe archive member: {member.name}")
        tar.extractall(base)


def load_model(url_or_dir: str = DEFAULT_MODEL_URL, models_root: str | None = None) -> str:
    """Return a local model directory.

    If ``url_or_dir`` names an existing directory it is used as-is. Otherwise it is
    treated as the pinned tarball URL and downloaded+extracted exactly once into
    ``models_root`` (default $STT_MODELS_DIR or /models); later calls short-circuit.
    Local names derive from the URL's basename so two different sources (streaming
    vs offline) never collide in the shared volume.
    """
    local = Path(url_or_dir)
    if local.is_dir():
        return str(_resolve_model_dir(local))

    from urllib.parse import urlparse

    source_name = Path(urlparse(url_or_dir).path).name or MODEL_DIR_NAME
    stem = source_name.replace(".tar.bz2", "")

    root = Path(models_root or _models_root())
    marker = root / f".{stem}.ready"
    final = root / stem
    if marker.is_file() and (final / "tokens.txt").is_file():
        return str(final)

    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".extract-{stem}"
    if staging.exists():
        shutil.rmtree(staging)
    archive = root / source_name
    if not archive.is_file():
        logger.info("downloading model %s", url_or_dir)
        part = archive.with_suffix(".part")
        with urllib.request.urlopen(url_or_dir, timeout=MODEL_DOWNLOAD_TIMEOUT_S) as resp, open(part, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        part.rename(archive)
    logger.info("extracting %s", archive)
    _safe_extract(archive, staging)

    extracted = _resolve_model_dir(staging)
    if final.exists():
        shutil.rmtree(final)
    shutil.move(str(extracted), str(final))
    shutil.rmtree(staging, ignore_errors=True)
    archive.unlink(missing_ok=True)
    marker.write_text(url_or_dir)
    logger.info("model ready at %s", final)
    return str(final)


def _pick_component(model_dir: Path, prefix: str) -> str:
    int8 = sorted(model_dir.glob(f"{prefix}*.int8.onnx"))
    plain = sorted(model_dir.glob(f"{prefix}*.onnx"))
    candidates = int8 or plain
    if not candidates:
        raise FileNotFoundError(f"no {prefix}*.onnx under {model_dir}")
    return str(candidates[0])


class _Engine:
    """One shared OnlineRecognizer; streams are created per connection."""

    def __init__(self, model_dir: str, num_threads: int):
        import sherpa_onnx

        d = Path(model_dir)
        endpointing_s = max(int(os.getenv("STT_ENDPOINTING_MS", "300")), 50) / 1000.0
        # rule2 mirrors the backend's endpointing=300ms LiveOption
        # (backend/utils/stt/streaming.py:844).
        self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(d / "tokens.txt"),
            encoder=_pick_component(d, "encoder"),
            decoder=_pick_component(d, "decoder"),
            joiner=_pick_component(d, "joiner"),
            num_threads=num_threads,
            sample_rate=SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=2.4,
            rule2_min_trailing_silence=endpointing_s,
            rule3_min_utterance_length=20,
        )
        logger.info(
            "OnlineRecognizer ready (model=%s threads=%d endpointing=%.2fs)",
            d.name,
            num_threads,
            endpointing_s,
        )


_ENGINES: dict[tuple[str, int], _Engine] = {}
_ENGINES_LOCK = threading.Lock()


def get_engine(model_dir: str, num_threads: int = 2) -> _Engine:
    key = (str(model_dir), num_threads)
    with _ENGINES_LOCK:
        engine = _ENGINES.get(key)
        if engine is None:
            engine = _Engine(model_dir, num_threads)
            _ENGINES[key] = engine
        return engine


def pcm16_to_float32(pcm: bytes):
    import numpy as np

    usable = len(pcm) - (len(pcm) % 2)
    arr = np.frombuffer(pcm[:usable], dtype=np.int16).astype("float32") / 32768.0
    return arr


def _result_text(result) -> str:
    text = result if isinstance(result, str) else getattr(result, "text", "")
    return (text or "").strip()


class ViRecognizer:
    """Per-connection streaming recognizer over the shared engine.

    transcribe_chunk feeds one binary PCM16 frame and returns final segments
    ([{text, is_final, start, duration}]) emitted on endpoint detection;
    flush() force-emits whatever hypothesis remains buffered.
    """

    def __init__(self, model_dir: str, num_threads: int = 2):
        self._engine = get_engine(model_dir, num_threads)
        self._stream = None
        self._total_samples = 0
        self._emitted_seconds = 0.0

    def _current_stream(self):
        if self._stream is None:
            self._stream = self._engine.recognizer.create_stream()
        return self._stream

    def _drain(self, stream) -> None:
        rec = self._engine.recognizer
        while rec.is_ready(stream):
            decode = getattr(rec, "decode_streams", None)
            if decode is not None:
                decode([stream])
            else:  # older wheels expose only decode_stream
                rec.decode_stream(stream)

    def _take_current(self, stream, total_seconds: float) -> dict | None:
        text = _result_text(self._engine.recognizer.get_result(stream))
        self._engine.recognizer.reset(stream)
        if not text:
            return None
        segment = {
            "text": text,
            "is_final": True,
            "start": round(self._emitted_seconds, 3),
            "duration": round(max(total_seconds - self._emitted_seconds, 0.0), 3),
        }
        self._emitted_seconds = total_seconds
        return segment

    def transcribe_chunk(self, pcm: bytes) -> list[dict]:
        if not pcm:
            return []
        samples = pcm16_to_float32(pcm)
        stream = self._current_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        self._total_samples += len(samples)
        self._drain(stream)
        total_seconds = self._total_samples / SAMPLE_RATE
        if not self._engine.recognizer.is_endpoint(stream):
            return []
        segment = self._take_current(stream, total_seconds)
        return [segment] if segment else []

    def flush(self) -> list[dict]:
        """Force-finalize buffered audio without dropping connection context.

        sherpa-onnx has no mid-stream partial flush, so this emits the current
        hypothesis and resets the stream Ã¢â‚¬â€ trading a little acoustic context to
        guarantee no words are ever duplicated across the Finalize boundary.
        """
        stream = self._current_stream()
        self._drain(stream)
        total_seconds = self._total_samples / SAMPLE_RATE
        segment = self._take_current(stream, total_seconds)
        return [segment] if segment else []

    def interim_text(self) -> str:
        if self._stream is None:
            return ""
        return _result_text(self._engine.recognizer.get_result(self._stream))

class _OfflineEngine:
    """Shared OfflineRecognizer (SOTA Vietnamese 30M) + Silero VAD.

    "Simulated streaming": audio is buffered through the VAD; when the VAD
    closes an utterance, the whole segment is decoded at once (RTF ~0.1, so a
    10 s utterance decodes in ~1 s on one core). Final transcripts therefore
    arrive at utterance boundaries - which matches how the backend consumes
    them anyway (interim_results=False in streaming.py:841).
    """

    def __init__(self, model_dir: str, num_threads: int):
        import sherpa_onnx

        d = Path(model_dir)
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            tokens=str(d / "tokens.txt"),
            encoder=_pick_component(d, "encoder"),
            decoder=str(d / "decoder.onnx") if (d / "decoder.onnx").is_file() else _pick_component(d, "decoder"),
            joiner=_pick_component(d, "joiner"),
            num_threads=num_threads,
            sample_rate=SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
        )
        vad_model = _models_root() / "silero_vad.onnx"
        if not vad_model.is_file():
            vad_model.parent.mkdir(parents=True, exist_ok=True)
            logger.info("downloading Silero VAD model")
            urllib.request.urlretrieve(SILERO_VAD_URL, vad_model)
        vad_config = sherpa_onnx.VadModelConfig()
        vad_config.silero_vad.model = str(vad_model)
        vad_config.silero_vad.threshold = float(os.getenv("STT_VAD_THRESHOLD", "0.5"))
        vad_config.silero_vad.min_speech_duration = 0.25
        vad_config.silero_vad.min_silence_duration = 0.45
        vad_config.sample_rate = SAMPLE_RATE
        # Per-connection VAD instances are cheap; keep one template config here.
        self.vad_config = vad_config
        logger.info("OfflineRecognizer ready (model=%s threads=%d)", d.name, num_threads)


class ViOfflineRecognizer:
    """Per-connection VAD-segmented offline recognizer (same interface as
    ViRecognizer: transcribe_chunk / flush / interim_text).

    Buffer design: every accepted sample is appended to ``_buffer``; when the
    VAD closes an utterance [abs_start, abs_start+n) the consumed prefix is
    dropped from the buffer and a final segment is emitted. flush() decodes
    whatever remains (no reliance on VAD.front, whose reference is only valid
    until the next VAD call).
    """

    def __init__(self, engine: "_OfflineEngine", total_budget_seconds: float = 120.0):
        import sherpa_onnx

        self._engine = engine
        # Wheel 1.13.x exposes the VAD wrapper as VoiceActivityDetector
        # (accept_waveform/empty/front/pop/flush/is_speech_detected).
        self._vad = sherpa_onnx.VoiceActivityDetector(
            engine.vad_config, buffer_size_in_seconds=total_budget_seconds
        )
        self._total_samples = 0
        self._buffer: list = []
        self._buf_start = 0  # absolute sample index of _buffer[0]

    def transcribe_chunk(self, pcm: bytes) -> list[dict]:
        if not pcm:
            return []
        samples = pcm16_to_float32(pcm)
        self._buffer.extend(samples)
        self._vad.accept_waveform(samples)
        self._total_samples += len(samples)
        return self._decode_ready_segments()

    def flush(self) -> list[dict]:
        """Emit whatever speech remains buffered as one final segment."""
        out = self._decode_ready_segments()
        remaining = len(self._buffer)
        if remaining > int(SAMPLE_RATE * 0.15):
            text = self._decode_samples(self._buffer)
            if text:
                out.append({
                    "text": text,
                    "is_final": True,
                    "start": round(self._buf_start / SAMPLE_RATE, 3),
                    "duration": round(remaining / SAMPLE_RATE, 3),
                })
        self._vad.flush()
        self._buffer = []
        self._buf_start = self._total_samples
        return [s for s in out if s["text"]]

    def interim_text(self) -> str:
        # Offline decoding has no interim hypothesis by definition.
        return ""

    def _decode_ready_segments(self) -> list[dict]:
        out: list[dict] = []
        while not self._vad.empty():
            segment = self._vad.front
            # front's reference is only valid until the next VAD method call:
            # copy what we need BEFORE pop() (doc: sherpa .front note).
            seg_samples = list(segment.samples)
            abs_start, n_samples = segment.start, len(segment.samples)
            self._vad.pop()
            text = self._decode_samples(seg_samples)
            if not text:
                continue
            start = abs_start / SAMPLE_RATE
            duration = n_samples / SAMPLE_RATE
            # Drop the decoded prefix from our buffer.
            drop = abs_start + n_samples - self._buf_start
            if drop > 0:
                del self._buffer[:drop]
                self._buf_start = abs_start + n_samples
            out.append({
                "text": text,
                "is_final": True,
                "start": round(start, 3),
                "duration": round(duration, 3),
            })
        return out

    def _decode_samples(self, samples) -> str:
        rec = self._engine.recognizer
        stream = rec.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        rec.decode_stream(stream)
        text = (_result_text(stream.result.text)).strip()
        # The VietASR 70k-hour model emits ALL-UPPERCASE tokens. Normalize to
        # sentence case so transcripts stay readable (proper nouns lose their
        # capitals — acceptable next to a wall of shouting text).
        if text.isupper():
            text = text.capitalize()
        return text


_OFFLINE_ENGINE: "_OfflineEngine | None" = None


def load_offline_engine(model_url_or_dir: str | None = None, num_threads: int = 2) -> "_OfflineEngine":
    """Build the shared offline engine from STT_MODEL_SOURCE or the pinned SOTA URL."""
    global _OFFLINE_ENGINE
    source = model_url_or_dir or os.getenv("STT_MODEL_SOURCE", OFFLINE_MODEL_URL)
    model_dir = load_model(source)
    _OFFLINE_ENGINE = _OfflineEngine(model_dir=model_dir, num_threads=num_threads)
    return _OFFLINE_ENGINE
