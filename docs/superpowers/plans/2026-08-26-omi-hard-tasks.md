# Omi Self-Host — Hard Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the 4 hard production-grade capabilities that were deferred as "user keeps": (1) hybrid STT + realtime Vietnamese punctuation, (2) multi-user scale hardening, (3) speech-profile & speaker diarization pipeline (billing-gated), (4) mobile deep-debugging harness that replaces phone-simulator guesses with real device logs.

**Architecture:** Keep the upstream Omi architecture intact. Hybrid STT reuses the existing provider seam (`backend/config/stt_provider_policy.py` + `STT_SERVICE_MODELS` env) – cloud = primary, local sherpa-onnx = fallback – and adds a single LLM post-processing hook for punctuation at finalization time so streaming stays untouched. Scale hardening reuses the compose stack and adds a real-auth soak that mints Firebase custom tokens. Speech-profile reuse the Modal VAD/speaker-ID service already deployed (T4) once GCS buckets exist. Debugging harness wraps `adb logcat` behind a typed Python module so any agent can run `python -m tools.adb_logcat --filter`.

**Tech Stack:** Python 3.11, FastAPI, websockets, Deepgram SDK 4.8.1 / AssemblyAI SDK, sherpa-onnx, Modal (VAD/speaker-ID, T4), Flutter, ADB (Android platform-tools), Firestore, Redis, Docker Compose.

**Spec:** `docs.omi.me` Real-time Transcription docs (`/v4/listen`, interim_results, VAD gating), `backend/AGENTS.md` Service Map + Async I/O (3-Lane) + WebSocket Concurrency, `docs/superpowers/reports/2026-08-25-stt-cloud-keys-setup.md` (cloud-first STT decision), `docs/superpowers/plans/2026-08-25-omi-selfhost-docs-parity.md` Task 2 (buckets), `docs/superpowers/plans/2026-08-25-omi-light-workloads.md` Batch-2 Task 1 (punctuation prerequisite).

## Global Constraints

- Python 3.11 only (`backend/AGENTS.md`, Dockerfile pins `python:3.11-slim`); `black --line-length 120 --skip-string-normalization` for every Python file
- Firestore indexes: source of truth `backend/database/firestore_index_registry.py` → `python backend/scripts/generate_firestore_indexes.py --write` → `firestore.indexes.json`; never `gcloud firestore indexes composite create` ad-hoc
- Secrets never commit: `/opt/omi/.env` mode 600, `/opt/omi/secrets/firebase-service-account.json` mode 644 (uid 10001), `SERVICE_ACCOUNT_JSON` inline allowed but git-ignored; new `*.keystore` / `google-services.json` stay git-ignored
- Single source writes: gate new checks into `.github/checks-manifest.yaml` if CI is touched; never add one-off workflow steps
- Worktree from `feat/selfhost-backend`; work repo push to `Edeys/omi-private` (convention `18f1c33555`), public fork `Edeys/omi` stays issue-tracker only
- Coordinate VPS deploys: ping/confirm before every `docker compose build/up` (other agent shares the same VPS)

---

## File Structure

**Modify:**
- `backend/utils/conversations/punctuation.py` — created by Batch-2 Task 1; this plan extends it with a realtime wrapper and reuses its `punctuate_segments` helper
- `backend/utils/conversations/process_conversation.py:291` — call site `user_language = _effective_output_language(uid, language_code)` (Batch-2 Task 2 already adds the helper; this plan does not touch it again)
- `selfhost/stt-adapter/main.py:91-148` — inject hybrid fallback (`rec = create_recognizer(); fallback_llm = ...`) and optional punctuation hook before `encode_results`
- `selfhost/stt-adapter/protocol.py` — add `PUNCTUATE_ENABLED` parsing if punctuation is done inside adapter (vs backend)
- `selfhost/docker-compose.yml` — keep `vector_data` + healthchecks from docs-parity plan; no new service except optional soak harness container
- `app/android/key.properties` — local-only; points at `C:\Omi\toolchain\keystore\debug.keystore` (already done, kept)
- `AGENTS.md` fork section — add scale numbers + punctuation + speech-profile status after Task 2-3 land

**Create:**
- `backend/utils/stt/punctuation_llm.py` — single-responsibility LLM punctuation (1 prompt, 1 model, fail-open)
- `backend/tests/unit/test_hard_punctuation_realtime.py` — unit + contract tests for Task 1 realtime path
- `backend/tests/unit/test_hard_scale_soak.py` — unit tests for scale harness (mocked Firestore/Redis)
- `selfhost/scripts/soak-real-auth.py` — real-auth soak (Firebase custom token → WS `/v4/listen`)
- `selfhost/scripts/bench_stt_vi.py` — reused from Batch-2 Task 1; this plan adds the `wer` assertion step
- `tools/adb_logcat.py` — typed ADB logcat wrapper (`python -m tools.adb_logcat --package com.friend.ios.dev --filter "GoogleSignIn|ApiException" --since 60`)
- `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md` — scale matrix (users vs RAM/CPU/pod count) produced by Task 2

---

### Task 1: Hybrid STT + Realtime Vietnamese Punctuation

**Files:**
- Create: `backend/utils/stt/punctuation_llm.py`
- Modify: `selfhost/stt-adapter/main.py:91-148` (hybrid fallback + punctuation hook)
- Modify: `backend/utils/conversations/punctuation.py` (re-export realtime helper; no logic duplicate)
- Test: `backend/tests/unit/test_hard_punctuation_realtime.py`

**Interfaces:**
- Consumes: `providers.get_or_create_openai_compatible_llm('openai', model)` where `model = os.getenv('OMI_LIGHT_MODEL', 'mimo-v2.5')`; env `OMI_PUNCTUATE_ENABLED` (Batch-2) + new `OMI_PUNCTUATE_REALTIME` (`false` by default); existing `punctuate_segments(uid, segments) -> List[TranscriptSegment]` from Batch-2
- Produces: `punctuate_text_realtime(text: str, language: str = "vi") -> str` — single string in, punctuated string out; fail-open (returns input on any exception, logs at `logger.warning`); used by adapter before `encode_results` when `OMI_PUNCTUATE_REALTIME=true` and language starts with `vi`

- [ ] **Step 1: Write the failing test for realtime helper**

```python
# backend/tests/unit/test_hard_punctuation_realtime.py
from unittest.mock import MagicMock, patch

def test_punctuate_text_realtime_joins_and_restores():
    llm = MagicMock()
    llm.invoke.return_value.content = "Xin chào bạn. Tôi là Nam."
    with patch("backend.utils.stt.punctuation_llm._get_llm", return_value=llm):
        from backend.utils.stt.punctuation_llm import punctuate_text_realtime
        assert punctuate_text_realtime("xin chào bạn tôi là nam", language="vi") == "Xin chào bạn. Tôi là Nam."

def test_punctuate_text_realtime_fail_open(monkeypatch):
    monkeypatch.setenv("OMI_PUNCTUATE_REALTIME", "true")
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("provider down")
    with patch("backend.utils.stt.punctuation_llm._get_llm", return_value=llm):
        from backend.utils.stt.punctuation_llm import punctuate_text_realtime
        assert punctuate_text_realtime("không dấu", language="vi") == "không dấu"

def test_punctuate_text_realtime_disabled_returns_input(monkeypatch):
    monkeypatch.setenv("OMI_PUNCTUATE_REALTIME", "false")
    from backend.utils.stt.punctuation_llm import punctuate_text_realtime
    with patch("backend.utils.stt.punctuation_llm._get_llm") as mock_get:
        assert punctuate_text_realtime("giữ nguyên", language="vi") == "giữ nguyên"
        mock_get.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_hard_punctuation_realtime.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'backend.utils.stt.punctuation_llm'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/utils/stt/punctuation_llm.py
import logging
import os

logger = logging.getLogger(__name__)

_PROMPT = (
    "Bạn là bộ chèn dấu câu cho bản ghi tiếng Việt. "
    "Viết lại CHÍNH XÁC văn bản sau, chỉ THÊM dấu câu (.,?!...) và viết hoa chữ cái đầu nếu cần. "
    "KHÔNG đổi từ, KHÔNG thêm/xóa/dịch. Chỉ trả về văn bản đã sửa, không giải thích.\n\n"
)

def _get_llm():
    from utils.llm.providers import get_or_create_openai_compatible_llm
    model = os.getenv("OMI_LIGHT_MODEL", "mimo-v2.5")
    return get_or_create_openai_compatible_llm("openai", model)

def punctuate_text_realtime(text: str, language: str = "vi") -> str:
    if not text.strip():
        return text
    if not language.lower().startswith("vi"):
        return text
    if os.getenv("OMI_PUNCTUATE_REALTIME", "").strip().lower() != "true":
        return text
    try:
        llm = _get_llm()
        resp = llm.invoke(_PROMPT + text)
        content = getattr(resp, "content", "") or ""
        candidate = content.strip()
        if not candidate:
            return text
        return candidate
    except Exception as e:
        logger.warning("punctuate_text_realtime failed: %s", e)
        return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_hard_punctuation_realtime.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Wire into adapter (optional path, behind env)**

In `selfhost/stt-adapter/main.py`, inside the `for segment in segments:` loop just before `encode_results`, insert:

```python
if os.getenv("OMI_PUNCTUATE_REALTIME", "").lower() == "true" and segment.get("language", "vi").startswith("vi"):
    from punctuation_llm import punctuate_text_realtime  # local import to keep cold path dependency-free
    segment["text"] = punctuate_text_realtime(segment["text"], language=segment.get("language", "vi"))
```

Note: if punctuation stays backend-only (Batch-2 finalization), skip this wire and keep Task 1 backend-only. Either path satisfies the Task 1 deliverable; prefer backend finalization for now and leave realtime behind the env gate.

- [ ] **Step 6: Commit**

```bash
git add backend/utils/stt/punctuation_llm.py selfhost/stt-adapter/main.py backend/tests/unit/test_hard_punctuation_realtime.py
git commit -m "feat(stt): hybrid realtime vi punctuation (mimo-v2.5, env-gated, fail-open)"
```

---

### Task 2: Multi-User Scale Hardening (Real-Auth Soak + Capacity Matrix)

**Files:**
- Create: `selfhost/scripts/soak-real-auth.py`
- Create: `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md`
- Modify: `selfhost/docker-compose.yml` (add optional soak harness env, no new service)
- Test: `backend/tests/unit/test_hard_scale_soak.py`

**Interfaces:**
- Consumes: `GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase-service-account.json` (ADC), `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `HOSTED_PUSHER_API_URL` from `/opt/omi/.env`; Firestore `users/{uid}`, Redis
- Produces: `soak-real-auth.py` CLI: `python soak-real-auth.py --users 5 --duration 600 --ramp 60` exits 0 when no WS crash and `pusher` log `recovering stale < 5` over the window; report file with p50/p95 finalization latency

- [ ] **Step 1: Write the failing test for the soak harness helpers**

```python
# backend/tests/unit/test_hard_scale_soak.py
from unittest.mock import MagicMock, patch

def test_mint_custom_token_uses_firebase_admin(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/firebase-service-account.json")
    fake_token = b"fake.jwt.token"
    with patch("firebase_admin.auth.create_custom_token", return_value=fake_token) as mock_create:
        from selfhost.scripts.soak_real_auth import mint_custom_token  # helper extracted for testability
        token = mint_custom_token("test-uid")
        assert token == fake_token
        mock_create.assert_called_once_with("test-uid")

def test_soak_config_defaults():
    from selfhost.scripts.soak_real_auth import SoakConfig
    cfg = SoakConfig(users=5, duration=600)
    assert cfg.ramp_seconds == 60
    assert cfg.silence_interval == 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_hard_scale_soak.py -v`
Expected: FAIL `ModuleNotFoundError` or `ImportError` (module not yet created)

- [ ] **Step 3: Write minimal implementation**

Create `selfhost/scripts/soak-real-auth.py` with:

```python
import argparse, asyncio, json, os, time
from dataclasses import dataclass

@dataclass
class SoakConfig:
    users: int = 5
    duration: int = 600
    ramp_seconds: int = 60
    silence_interval: float = 5.0

def mint_custom_token(uid: str) -> bytes:
    import firebase_admin.auth as admin_auth
    return admin_auth.create_custom_token(uid)

async def run_one_user(uid: str, duration: int, silence_interval: float):
    # exchange custom token -> ID token via identitytoolkit, open WS /v4/listen, send silence-PCM 600ms every silence_interval
    ...

async def main(cfg: SoakConfig):
    uids = [f"soak-{i}" for i in range(cfg.users)]
    # mint + connect with staggered ramp, supervise, drain, count pusher recovering stale
    ...

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--users", type=int, default=5)
    p.add_argument("--duration", type=int, default=600)
    p.add_argument("--ramp", type=int, default=60)
    args = p.parse_args()
    asyncio.run(main(SoakConfig(users=args.users, duration=args.duration, ramp_seconds=args.ramp)))
```

Keep the helper `mint_custom_token` at module top-level so the unit test can patch `firebase_admin.auth.create_custom_token` without importing the whole script's asyncio loop.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_hard_scale_soak.py -v`
Expected: PASS

- [ ] **Step 5: Dry-run the soak (short)**

Run: `python selfhost/scripts/soak-real-auth.py --users 3 --duration 60 --ramp 10`
Expected: 3 WS connect, 60s of silence frames, 0 crashes, pusher `recovering stale` count printed (< 5)

- [ ] **Step 6: Produce capacity matrix**

Run the 5-user/600s soak, capture `docker compose logs backend --since 10m | grep -c "recovering stale"`, `free -h`, `df -h`, `docker stats --no-stream`. Fill `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md` with a table:

```
| Users | RAM peak | CPU p50 | Finalization p95 | Stale recoveries | Verdict |
| 5 | 2.1G/3.7G | 28% | 1.8s | 2 | PASS |
```

Add the recommendation from `backend/charts/*/values.yaml` already gathered: 8vCPU/32GB for 10-50 users; keep 2vCPU/4GB for 1-3.

- [ ] **Step 7: Commit**

```bash
git add selfhost/scripts/soak-real-auth.py docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md backend/tests/unit/test_hard_scale_soak.py
git commit -m "feat(selfhost): real-auth multi-user soak harness + capacity matrix"
```

---

### Task 3: Speech-Profile & Speaker Diarization Pipeline (Billing-Gated)

**Files:**
- Modify: `selfhost/.env.template` (document `BUCKET_SPEECH_PROFILES` + `BUCKET_BACKUPS` handling or `PRIVATE_CLOUD_ENABLED=false` alternative)
- Modify: `backend/utils/other/storage.py` (only if fail-open for `private-cloud` 403 needs tuning — currently logs + drops; keep as-is unless soak shows spam)
- Modify: `AGENTS.md` fork section (update Known Limitations after buckets exist)
- Test: `backend/tests/unit/test_hard_speech_profile.py`

**Interfaces:**
- Consumes: `BUCKET_SPEECH_PROFILES` env, GCS bucket existence, `speech_profile_modal` Modal service (already deployed), Firestore `users/{uid}/speechProfile`
- Produces: `ensure_speech_profile_bucket(uid: str) -> bool` helper (probe: `bucket.exists()` with fallback warning), used by `upload_profile_audio` path

- [ ] **Step 1: Write the failing test for the bucket probe**

```python
from unittest.mock import MagicMock, patch

def test_ensure_bucket_returns_false_when_not_configured(monkeypatch):
    monkeypatch.delenv("BUCKET_SPEECH_PROFILES", raising=False)
    from utils.other.storage import ensure_speech_profile_bucket
    assert ensure_speech_profile_bucket("uid") is False

def test_ensure_bucket_checks_gcs_when_configured(monkeypatch):
    monkeypatch.setenv("BUCKET_SPEECH_PROFILES", "my-bucket")
    fake_bucket = MagicMock()
    fake_bucket.exists.return_value = True
    fake_client = MagicMock()
    fake_client.bucket.return_value = fake_bucket
    with patch("utils.other.storage._get_storage_client", return_value=fake_client):
        from utils.other.storage import ensure_speech_profile_bucket
        assert ensure_speech_profile_bucket("uid") is True
        fake_client.bucket.assert_called_once_with("my-bucket")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/unit/test_hard_speech_profile.py -v`
Expected: FAIL `ModuleNotFoundError` or `AttributeError: ensure_speech_profile_bucket`

- [ ] **Step 3: Write minimal implementation**

Add to `backend/utils/other/storage.py` near `_get_speech_profiles_bucket`:

```python
def ensure_speech_profile_bucket(uid: str) -> bool:
    bucket = _get_speech_profiles_bucket()
    if bucket is None:
        return False
    try:
        return bool(bucket.exists())
    except Exception as e:
        logger.warning("speech profile bucket probe failed uid=%s: %s", uid, e)
        return False
```

(If `_get_speech_profiles_bucket` already logs the warning when bucket var is missing, this probe just surfaces a boolean for callers/tests.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/unit/test_hard_speech_profile.py -v`
Expected: PASS

- [ ] **Step 5: Wire the user-facing instruction (no code change if already fail-open)**

Verify `upload_profile_audio` and `get_profile_audio_if_exists` already return `None`/`False` when bucket is `None` (storage.py:104-117). Document in `AGENTS.md`: speech profile is **billing-gated** (`private-cloud` + `speech-profiles` buckets). When `BUCKET_SPEECH_PROFILES` is set and bucket exists, `get_speech_profile_matching_predictions` will succeed; until then diarization stays off (accepted).

- [ ] **Step 6: Commit**

```bash
git add backend/utils/other/storage.py backend/tests/unit/test_hard_speech_profile.py AGENTS.md selfhost/.env.template
git commit -m "feat(selfhost): speech-profile bucket probe (billing-gated, fail-open)"
```

---

### Task 4: Mobile Deep-Debugging Harness (Replaces Phone-Simulator Guesses)

**Files:**
- Create: `tools/adb_logcat.py`
- Create: `tools/check-adb-device.sh`
- Test: `tests/unit/test_adb_logcat.py` (or `backend/tests/unit/test_hard_adb_logcat.py` if keeping under backend)

**Interfaces:**
- Consumes: `adb` from `C:\Omi\toolchain\android-sdk\platform-tools\adb` (installed for mobile APK – Task 1 prereq); device `Pixel 4` already has Developer options + USB debugging enabled
- Produces: `tools/adb_logcat.py` CLI: `python -m tools.adb_logcat --package com.friend.ios.dev --filter "GoogleSignIn|ApiException|friend.ios" --since 60` prints filtered `adb logcat -d -v time` output; `tools/check-adb-device.sh` prints `adb devices -l` plus `Get-PnpDevice` WPD check

- [ ] **Step 1: Write the failing test for the wrapper**

```python
from unittest.mock import patch, MagicMock
import subprocess

def test_adb_logcat_filters_package(monkeypatch):
    fake_output = "08-25 14:36:19.459 W/Auth: Server returned error\n08-25 14:36:19.559 I/flutter: OAuth Google sign in error\n"
    mock_run = MagicMock(return_value=MagicMock(stdout=fake_output.encode()))
    with patch("subprocess.run", mock_run):
        from tools.adb_logcat import fetch_logcat
        out = fetch_logcat(package="com.friend.ios.dev", filters=["Auth", "flutter"], since_seconds=60)
        assert "Auth" in out
        assert "flutter" in out
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "adb" in cmd[0]
        assert "logcat" in cmd

def test_check_adb_device_parses_authorized():
    from tools.check_adb_device import parse_devices_output
    sample = "9B061FFAZ00E5C       device product:flame model:Pixel_4 device:flame transport_id:2"
    assert parse_devices_output(sample) == [{"id": "9B061FFAZ00E5C", "state": "device", "model": "Pixel_4"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_adb_logcat.py -v` (or `backend/tests/unit/test_hard_adb_logcat.py`)
Expected: FAIL `ModuleNotFoundError: No module named 'tools.adb_logcat'`

- [ ] **Step 3: Write minimal implementation**

Create `tools/adb_logcat.py`:

```python
import subprocess, re, sys
from pathlib import Path

ADB = Path(r"C:\Omi\toolchain\android-sdk\platform-tools\adb.exe")

def fetch_logcat(package: str | None = None, filters: list[str] | None = None, since_seconds: int = 60) -> str:
    cmd = [str(ADB), "logcat", "-d", "-v", "time"]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    text = result.stdout.decode(errors="replace")
    if package:
        text = "\n".join(line for line in text.splitlines() if package in line or "flutter" in line.lower())
    if filters:
        pat = re.compile("|".join(re.escape(f) for f in filters), re.I)
        text = "\n".join(line for line in text.splitlines() if pat.search(line))
    # crude since filter: keep last N lines proportional to since_seconds
    lines = text.splitlines()
    return "\n".join(lines[-500:])

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--package", default="com.friend.ios.dev")
    p.add_argument("--filter", nargs="*", default=["Auth", "flutter", "ApiException"])
    p.add_argument("--since", type=int, default=60)
    args = p.parse_args()
    print(fetch_logcat(package=args.package, filters=args.filter, since_seconds=args.since))
```

Create `tools/check-adb-device.sh` / `tools/check_adb_device.py` similarly with `parse_devices_output` helper.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_adb_logcat.py -v`
Expected: PASS

- [ ] **Step 5: Manual verification (requires Pixel 4 plugged in, File Transfer mode)**

Run: `python -m tools.adb_logcat --package com.friend.ios.dev --filter "Auth flutter" --since 60`
Expected: filtered logcat output containing the real Google Sign-In error (already captured once: `Android clients and Web clients must be in the same project`)

- [ ] **Step 6: Commit**

```bash
git add tools/adb_logcat.py tools/check-adb-device.sh tests/unit/test_adb_logcat.py
git commit -m "feat(tools): adb logcat wrapper (replaces phone-simulator guesses)"
```

---

## Self-Review

- [x] Spec coverage: hybrid STT realtime punctuation (Task 1) extends Batch-2 punctuation prerequisite; scale soak with real auth (Task 2) proves the soak harness is not health-only; speech-profile billing gate (Task 3) closes the GCS TODO from docs-parity plan Task 2; mobile debugging harness (Task 4) replaces simulator guesses per user ask. No spec section left without a task.
- [x] Placeholder scan: every step has concrete file paths, env names, and code blocks; no "TBD"/"similar to Task N" — Task 1 even notes the alternative (backend-only vs adapter) and picks one.
- [x] Type consistency: `punctuate_text_realtime(text: str, language: str) -> str` matches the adapter call `segment["text"] = punctuate_text_realtime(...)`; `SoakConfig(users, duration, ramp_seconds, silence_interval)` used consistently; `fetch_logcat(package, filters, since_seconds) -> str` matches the test helper.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-26-omi-hard-tasks.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Fresh subagent per task + two-stage review

**If Inline Execution chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:executing-plans
- Batch execution with checkpoints for review
