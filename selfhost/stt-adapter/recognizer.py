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
# encoder_dims), so sherpa-onnx OnlineRecognizer cannot load it — verified by
# crash ('encoder_dims' does not exist in the metadata) and ONNX metadata
# inspection. The streaming multilingual vi-capable zipformer from the same
# release tag is the default; the offline 30M model stays selectable via
# STT_MODEL_SOURCE if an OfflineRecognizer path is ever added.
DEFAULT_MODELS_ROOT = "/models"
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
            if not str(target).startswith(str(base)):
                raise ValueError(f"refusing unsafe archive member: {member.name}")
        tar.extractall(base)


def load_model(url_or_dir: str = DEFAULT_MODEL_URL, models_root: str | None = None) -> str:
    """Return a local model directory.

    If ``url_or_dir`` names an existing directory it is used as-is. Otherwise it is
    treated as the pinned tarball URL and downloaded+extracted exactly once into
    ``models_root`` (default $STT_MODELS_DIR or /models); later calls short-circuit.
    """
    local = Path(url_or_dir)
    if local.is_dir():
        return str(_resolve_model_dir(local))

    root = Path(models_root or _models_root())
    marker = root / ".model-ready"
    if marker.is_file():
        try:
            resolved = _resolve_model_dir(root)
            if (resolved / "tokens.txt").is_file():
                return str(resolved)
        except FileNotFoundError:
            logger.warning("model marker present but files missing; re-downloading")

    root.mkdir(parents=True, exist_ok=True)
    staging = root / ".extract"
    if staging.exists():
        shutil.rmtree(staging)
    archive = root / f"{MODEL_DIR_NAME}.tar.bz2"
    if not archive.is_file():
        logger.info("downloading model %s", url_or_dir)
        part = archive.with_suffix(".part")
        urllib.request.urlretrieve(url_or_dir, part)
        part.rename(archive)
    logger.info("extracting %s", archive)
    _safe_extract(archive, staging)

    extracted = _resolve_model_dir(staging)
    final = root / MODEL_DIR_NAME
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
        hypothesis and resets the stream — trading a little acoustic context to
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
