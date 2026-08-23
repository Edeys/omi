import os
import struct
import time
from typing import Any


def wav_header(num_samples: int, sample_rate: int, channels: int = 1, bits: int = 16) -> bytes:
    data_size = num_samples * channels * (bits // 8)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, sample_rate * channels * (bits // 8), channels * (bits // 8), bits)
        + b"data"
        + struct.pack("<I", data_size)
    )


class AudioStore:
    """Per-uid PCM chunk storage with idle-based finalization into WAV files."""

    def __init__(self, base_dir: str, idle_finalize_seconds: int = 300) -> None:
        self.base_dir = base_dir
        self.idle_finalize_seconds = idle_finalize_seconds

    def _uid_dir(self, uid: str) -> str:
        safe = "".join(c for c in uid if c.isalnum() or c in "-_")[:64] or "unknown"
        path = os.path.join(self.base_dir, safe)
        os.makedirs(path, exist_ok=True)
        return path

    def _slot(self, now: float | None = None) -> str:
        now = now or time.time()
        return time.strftime("%Y%m%d-%H", time.gmtime(now))

    def _meta_path(self, pcm_path: str) -> str:
        return pcm_path + ".json"

    def append_chunk(self, uid: str, chunk: bytes, sample_rate: int, now: float | None = None) -> dict[str, Any]:
        now = now or time.time()
        directory = self._uid_dir(uid)
        slot = self._slot(now)
        pcm_path = os.path.join(directory, f"{slot}.pcm")
        is_new = not os.path.exists(pcm_path)
        if is_new:
            import json

            with open(self._meta_path(pcm_path), "w", encoding="utf-8") as fh:
                json.dump({"sample_rate": int(sample_rate), "created_at": now}, fh)
        with open(pcm_path, "ab") as fh:
            fh.write(chunk)
        return {"path": pcm_path, "bytes": len(chunk), "new_file": is_new}

    def stale_open_files(self, uid: str, now: float | None = None) -> list[str]:
        now = now or time.time()
        directory = self._uid_dir(uid)
        stale = []
        for name in os.listdir(directory):
            if not name.endswith(".pcm"):
                continue
            path = os.path.join(directory, name)
            if now - os.path.getmtime(path) > self.idle_finalize_seconds:
                stale.append(path)
        return stale

    def finalize(self, pcm_path: str) -> str | None:
        """Convert an accumulated .pcm into a playable .wav (same stem)."""
        import json

        if not os.path.exists(pcm_path):
            return None
        meta_path = self._meta_path(pcm_path)
        sample_rate = 16000
        if os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as fh:
                sample_rate = int(json.load(fh).get("sample_rate", 16000))
        size = os.path.getsize(pcm_path)
        num_samples = size // 2
        wav_path = pcm_path[:-4] + ".wav"
        header = wav_header(num_samples, sample_rate)
        with open(wav_path, "wb") as out:
            out.write(header)
            with open(pcm_path, "rb") as src:
                while True:
                    block = src.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
        os.remove(pcm_path)
        os.remove(meta_path)
        return wav_path

    def list_audio(self, uid: str) -> list[dict[str, Any]]:
        directory = self._uid_dir(uid)
        items = []
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                items.append(
                    {
                        "name": name,
                        "bytes": os.path.getsize(path),
                        "modified": os.path.getmtime(path),
                    }
                )
        return items

    def read_wav(self, uid: str, filename: str) -> bytes | None:
        safe_name = os.path.basename(filename)
        if not safe_name.endswith(".wav"):
            return None
        path = os.path.join(self._uid_dir(uid), safe_name)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as fh:
            return fh.read()
