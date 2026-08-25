#!/usr/bin/env python
"""STT benchmark tiếng Việt — Deepgram Nova-3 vs AssemblyAI Universal vs sherpa-onnx local.

Chạy TRÊN VPS (cần: keys DEEPGRAM_API_KEY / ASSEMBLYAI_API_KEY trong môi trường,
docker container compose-stt-adapter-1 cho engine local).

Usage:
    python stt_benchmark.py --samples-dir ./benchmark_samples --out results.json

Mỗi mẫu = cặp file `<name>.<mp3|wav>` + `<name>.ref.txt` (text tham chiếu có dấu).
Engine local yêu cầu wav PCM16 16kHz mono (convert bằng ffmpeg trước khi chạy).
Latency chỉ tính thời gian xử lý (không tính upload/poll wait theo đúng nghĩa có thể).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.request
import wave
from pathlib import Path

DEEPGRAM_URL_TMPL = ("https://api.deepgram.com/v1/listen?model={model}&language={lang}&punctuate=true")
DEEPGRAM_CONFIGS = [("nova-3", "multi"), ("nova-3", "vi"), ("nova-2", "vi")]
ASSEMBLY_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
ASSEMBLY_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
STT_ADAPTER_CONTAINER = os.getenv("STT_ADAPTER_CONTAINER", "compose-stt-adapter-1")
CONTAINER_BENCH_DIR = "/tmp/bench"

CONTENT_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4"}


def _http(method: str, url: str, *, headers: dict | None = None, data: bytes | None = None,
          timeout: int = 120) -> tuple[int, dict | bytes]:
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            return resp.status, json.loads(body) if "json" in ctype else body
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# ---------------------------------------------------------------- engines
def run_deepgram(audio: bytes, ext: str, key: str, model: str, lang: str) -> dict:
    url = DEEPGRAM_URL_TMPL.format(model=model, lang=lang)
    t0 = time.perf_counter()
    status, body = _http("POST", url,
                         headers={"Authorization": f"Token {key}",
                                  "Content-Type": CONTENT_TYPES.get(ext, "application/octet-stream")},
                         data=audio)
    elapsed = time.perf_counter() - t0
    if status != 200:
        return {"ok": False, "error": f"HTTP {status}: {str(body)[:200]}", "latency_s": round(elapsed, 2)}
    text = " ".join(alt.get("transcript", "") for ch in body["results"]["channels"]
                    for alt in ch["alternatives"])
    return {"ok": True, "transcript": text.strip(), "latency_s": round(elapsed, 2),
            "audio_duration_s": body["metadata"].get("duration")}


def _safe_print(entry: dict, engine: str) -> None:
    r = entry["engines"][engine]
    if not r.get("ok"):
        print(f"  {engine:24s}: FAIL {r.get('error', '')[:100]}")
        return
    print(f"  {engine:24s}: wer={r.get('wer')} lat={r['latency_s']}s :: {r.get('transcript', '')[:80]}")


def run_assemblyai(audio: bytes, key: str) -> dict:
    # upload không tính vào latency xử lý
    status, up = _http("POST", ASSEMBLY_UPLOAD_URL,
                       headers={"authorization": key, "content-type": "application/octet-stream"},
                       data=audio)
    if status != 200:
        return {"ok": False, "error": f"upload HTTP {status}: {str(up)[:200]}"}
    t0 = time.perf_counter()
    status, tr = _http("POST", ASSEMBLY_TRANSCRIPT_URL,
                       headers={"authorization": key, "content-type": "application/json"},
                       data=json.dumps({"audio_url": up["upload_url"], "speech_models": ["universal"]}).encode())
    if status not in (200, 201):
        return {"ok": False, "error": f"transcript HTTP {status}: {str(tr)[:200]}"}
    tid = tr["id"]
    polls = 0
    while True:
        status, res = _http("GET", f"{ASSEMBLY_TRANSCRIPT_URL}/{tid}", headers={"authorization": key})
        polls += 1
        if status == 200 and res.get("status") == "completed":
            # trừ overhead poll gần nhất để xấp xỉ thời gian xử lý thuần
            elapsed = time.perf_counter() - t0 - 1.0  # poll interval 1s
            return {"ok": True, "transcript": res["text"].strip(),
                    "latency_s": round(max(elapsed, 0.01), 2), "polls": polls}
        if status == 200 and res.get("status") == "error":
            return {"ok": False, "error": res.get("error", "unknown")}
        time.sleep(1.0)


LOCAL_RUNNER = r'''
import json, sys, time, wave
sys.path.insert(0, "/srv")
import recognizer
engine = recognizer.load_offline_engine()
rec = recognizer.ViOfflineRecognizer(engine)
path = sys.argv[1]
with wave.open(path, "rb") as w:
    assert w.getframerate() == 16000 and w.getnchannels() == 1, "cần wav 16k mono"
    pcm = w.readframes(w.getnframes())
t0 = time.perf_counter()
segs = rec.transcribe_chunk(pcm) + rec.flush()
elapsed = time.perf_counter() - t0
text = "".join(s.get("text", "") for s in segs).strip()
print(json.dumps({"ok": True, "transcript": text, "latency_s": round(elapsed, 3)}))
'''


def run_local(wav_path: Path) -> dict:
    """Chạy offline recognizer bên trong container stt-adapter (file đã được mount/copy trước)."""
    remote = f"{CONTAINER_BENCH_DIR}/{wav_path.name}"
    t0 = time.perf_counter()
    proc = subprocess.run(
        ["docker", "exec", STT_ADAPTER_CONTAINER, "python", "-c", LOCAL_RUNNER, remote],
        capture_output=True, text=True, timeout=600)
    exec_overhead = time.perf_counter() - t0
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[-300:]}
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    # trừ overhead khởi động python container (đo lần chạy không engine riêng biệt khó,
    # ghi kèm cả wall-time để minh bạch)
    out["exec_wall_s"] = round(exec_overhead, 2)
    return out


# ---------------------------------------------------------------- helpers
def normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in unicodedata.normalize("NFC", text) if not unicodedata.category(ch).startswith("P"))
    return re.sub(r"\s+", " ", text).strip()


def wer(reference: str, hypothesis: str) -> float | None:
    import jiwer
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return None
    return round(jiwer.wer(ref, hyp), 4)


def ensure_wav16k(path: Path, tmpdir: Path) -> Path:
    if path.suffix.lower() == ".wav":
        return path
    out = tmpdir / (path.stem + "_16k.wav")
    subprocess.run(["ffmpeg", "-y", "-i", str(path), "-ar", "16000", "-ac", "1",
                    "-sample_fmt", "s16", str(out)], check=True, capture_output=True)
    return out


def push_to_container(f: Path) -> None:
    subprocess.run(["docker", "exec", STT_ADAPTER_CONTAINER, "mkdir", "-p", CONTAINER_BENCH_DIR],
                   check=True, capture_output=True)
    subprocess.run(["docker", "cp", str(f), f"{STT_ADAPTER_CONTAINER}:{CONTAINER_BENCH_DIR}/"],
                   check=True, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples-dir", required=True)
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    assembly_key = os.getenv("ASSEMBLYAI_API_KEY", "")
    samples_dir = Path(args.samples_dir)

    refs = sorted(samples_dir.glob("*.ref.txt"))
    if not refs:
        print("Không tìm thấy mẫu nào (*.ref.txt)", file=sys.stderr)
        return 1

    results = {}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for ref in refs:
            name = ref.stem.removesuffix(".ref")
            audio_src = next((p for p in samples_dir.iterdir()
                              if p.stem == name and p.suffix.lower() in CONTENT_TYPES), None)
            if audio_src is None:
                print(f"[skip] {name}: thiếu file audio", file=sys.stderr)
                continue
            reference = ref.read_text(encoding="utf-8").strip()
            wav16k = ensure_wav16k(audio_src, td)
            audio_bytes = audio_src.read_bytes()
            print(f"\n=== {name} ({audio_src.name}, {len(audio_bytes)//1024}KB) ===")
            entry = {"reference": reference, "file": audio_src.name, "engines": {}}

            if deepgram_key:
                for model, lang in DEEPGRAM_CONFIGS:
                    r = run_deepgram(audio_bytes, audio_src.suffix.lower(), deepgram_key, model, lang)
                    r["wer"] = wer(reference, r.get("transcript", "")) if r["ok"] else None
                    engine_name = f"deepgram_{model}_{lang}".replace("_multi", "_multi")
                    entry["engines"][engine_name] = r
                    _safe_print(entry, engine_name)

            if assembly_key:
                try:
                    r = run_assemblyai(audio_bytes, assembly_key)
                except Exception as e:  # không để 1 engine chết làm hỏng cả benchmark
                    r = {"ok": False, "error": f"exception: {e}"}
                r["wer"] = wer(reference, r.get("transcript", "")) if r.get("ok") else None
                entry["engines"]["assemblyai_universal"] = r
                _safe_print(entry, "assemblyai_universal")

            push_to_container(wav16k)
            push_to_container(ref)
            try:
                r = run_local(wav16k)
            except Exception as e:
                r = {"ok": False, "error": f"exception: {e}"}
            r["wer"] = wer(reference, r.get("transcript", "")) if r.get("ok") else None
            entry["engines"]["sherpa_local"] = r
            _safe_print(entry, "sherpa_local")

            results[name] = entry

    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
