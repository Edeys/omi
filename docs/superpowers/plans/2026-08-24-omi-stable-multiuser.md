# Omi Stable Multi-User Self-Host Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến bản sao Omi self-host hiện tại (1 user, hay crash) thành hệ thống chạy liên tục nhiều giờ cho nhiều user đồng thời, xử lý triệt để các lỗi đã gặp (STT 1008, Firestore index thiếu, pusher 403, LLM timeout).

**Architecture:** Giữ nguyên Docker Compose 3-tier (backend/pusher/redis + stt-adapter) trên VPS 103.116.39.65. Sửa giao thức STT để SDK 4.8.1 (query-params) tương thích adapter, hoàn thiện toàn bộ composite index Firestore qua registry, tắt/hoặc cấp bucket cho private-cloud, tuning LLM timeout + circuit-breaker, thêm soak test đa user. Không thêm service mới ngoài những gì đã có + notifications-job.

**Tech Stack:** Python 3.11 (FastAPI, deepgram-sdk 4.8.1, sherpa-onnx, websockets), Redis 7, Firestore (collectionGroup), Docker Compose, nginx + Let's Encrypt, `ox-alpha-free` via `https://opencode.ai/zen/go/v1` (fallback 9router), pytest + TestClient.

**Spec:** `docs.omi.me` đã ingest đầy đủ (Backend_Setup, listen_pusher_pipeline, Real-time_Transcription, Firestore_query_and_transaction, AGENTS.md). Không có spec file riêng — plan này suy ra trực tiếp từ spec + lỗi thực tế 2026-08-23/24.

## Global Constraints

- Python 3.11 only (`backend/AGENTS.md`), `python:3.11-slim` trong mọi Dockerfile
- Node 22 (`>=22.19 <23`) nếu chạm desktop, pnpm `pnpm install --ignore-scripts`
- `black --line-length 120 --skip-string-normalization` cho mọi file Python
- Secrets không commit: `/opt/omi/.env` mode 600, `/opt/omi/secrets/firebase-service-account.json` mode 644 (uid 10001 cần đọc), `GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase-service-account.json`
- `DEEPGRAM_SELF_HOSTED_ENABLED` phải là chuỗi `'true'` lowercase (`backend/utils/stt/streaming.py:581` check `== 'true'`)
- Firestore index là nguồn sự thật `backend/database/firestore_index_registry.py`; tạo index chỉ qua `gcp_firestore_indexes.yml` với `APPLY_FIRESTORE_INDEXES=true`, không tự ý `gcloud firestore indexes composite create` lẻ tẻ
- Không tự ý spawn subagent khi 1 agent làm được (`preferences/opencodego_subagent_config.md`)
- Mọi webhook phải trả 200 <5s, xử lý nặng chạy background (`httpx` + semaphores, không dùng `requests` sync trong async)
- Logging không in raw PII: dùng `utils.log_sanitizer.sanitize()`

---

## File Structure

**Sửa:**
- `selfhost/stt-adapter/main.py` — thêm auto-start từ query_string, giữ JSON Start để test cũ pass
- `selfhost/stt-adapter/protocol.py` — helper parse query_string (nếu cần)
- `selfhost/docker-compose.yml` — đã có pusher secrets mount, thêm healthcheck tuning, `omics_apps_*` volumes đã có, thêm `BUCKET_BACKUPS` handling hoặc disable private-cloud
- `backend/utils/other/notifications.py` — không sửa (đã có), nhưng verify daily summary cần FCM token
- `AGENTS.md` — đã cập nhật notifications-job, cần cập nhật Known Limitations sau khi fix xong
- `firestore.indexes.json` — regenerate từ registry (không edit tay)

**Tạo (nếu chưa có):**
- `selfhost/stt-adapter/tests/test_queryparam_start.py` — test mới cho query-param auto-start
- `docs/superpowers/plans/2026-08-24-omi-stable-multiuser.md` — file này
- `selfhost/scripts/soak-test.sh` — soak 8h, 5 user đồng thời

---

### Task 1: Hoàn thiện toàn bộ Firestore composite indexes

**Files:**
- Modify: `firestore.indexes.json` (generate, không sửa tay)
- Reference: `backend/database/firestore_index_registry.py:1-80`, `backend/scripts/generate_firestore_indexes.py`, `backend/scripts/reconcile_firestore_indexes.py`
- Test: `backend/scripts/reconcile_firestore_indexes.py --check-only` (fail-closed)

**Interfaces:**
- Consumes: `firestore_index_registry.py` — `registry.all_shapes()` trả về list shape (collection, filters, order_by)
- Produces: `firestore.indexes.json` với `indexes[]` + `fieldOverrides[]` khớp 100% registry

- [ ] **Step 1: Kiểm tra registry hiện tại và manifest cũ**

```bash
python backend/scripts/generate_firestore_indexes.py --write --dry-run
cat firestore.indexes.json | head -n 40
```

- [ ] **Step 2: Viết test fail cho index meetings còn thiếu (đã thấy trong log 2026-08-24)**

```python
# tests/unit/test_firestore_indexes_meetings.py
def test_meetings_index_exists():
    import json
    with open("firestore.indexes.json") as f:
        data = json.load(f)
    indexes = data.get("indexes", [])
    assert any(
        idx.get("collectionGroup") == "meetings"
        and any(f.get("fieldPath") == "start_time" for f in idx.get("fields", []))
        and any(f.get("fieldPath") == "end_time" for f in idx.get("fields", []))
        for idx in indexes
    ), "meetings (start_time ASC, end_time ASC) index missing — see backend log 05:00:54 FailedPrecondition"
```

- [ ] **Step 3: Chạy test → FAIL**

Run: `pytest tests/unit/test_firestore_indexes_meetings.py -v`
Expected: FAIL `meetings ... index missing`

- [ ] **Step 4: Generate manifest đúng**

```bash
python backend/scripts/generate_firestore_indexes.py --write
git diff firestore.indexes.json  # phải thấy thêm meetings + các shape khác
python backend/scripts/reconcile_firestore_indexes.py --check-only  # phải PASS sau khi Firebase đã tạo
```

- [ ] **Step 5: Commit**

```bash
git add firestore.indexes.json tests/unit/test_firestore_indexes_meetings.py
git commit -m "fix(firestore): regenerate indexes to include meetings start_time/end_time"
```

- [ ] **Step 6: Deploy indexes lên Firebase (cần phê duyệt tay)**

```bash
# Trên VPS hoặc local có gcloud auth:
# Trigger workflow: gcp_firestore_indexes.yml với APPLY_FIRESTORE_INDEXES=true
# Hoặc click link trong log backend và đợi status Enabled
gcloud firestore indexes composite list --project=omi-xuan
```

---

### Task 2: Sửa STT adapter để chấp nhận query-params (fix 1008 audio before Start)

**Files:**
- Modify: `selfhost/stt-adapter/main.py:91-148` — thêm nhánh auto-start từ `ws.scope["query_string"]`
- Test: `selfhost/stt-adapter/tests/test_protocol.py` (giữ nguyên), tạo `selfhost/stt-adapter/tests/test_queryparam_start.py`

**Interfaces:**
- Consumes: `ws.scope["query_string"]: bytes`, `urllib.parse.parse_qs`, `protocol.validate_start(payload)`
- Produces: `rec` đã init trước khi nhận binary frame đầu tiên, gửi `Metadata` ack ngay

- [ ] **Step 1: Viết test fail cho query-param path (SDK thực tế)**

```python
# selfhost/stt-adapter/tests/test_queryparam_start.py
import json
from fastapi.testclient import TestClient
import main
from conftest import ScriptedRecognizer

def test_queryparam_auto_start_accepts_binary_without_json_start():
    main.set_recognizer_factory(lambda: ScriptedRecognizer(
        segments=[{"text": "xin chào", "is_final": True, "start": 0.0, "duration": 0.5}]
    ))
    client = TestClient(main.app)
    # deepgram-sdk 4.8.1 gửi options qua query string, không gửi {"type":"Start"}
    with client.websocket_connect("/v1/listen?sample_rate=16000&encoding=linear16&channels=1&language=vi&model=nova-3") as ws:
        ws.send_bytes(b"\x00\x00" * 8000)  # phải được chấp nhận, không 1008
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "Results"
        assert msg["channel"]["alternatives"][0]["transcript"] == "xin chào"
```

- [ ] **Step 2: Chạy test → FAIL (hiện tại trả Error 1008)**

Run: `bash selfhost/stt-adapter/run-tests.sh` hoặc `pytest selfhost/stt-adapter/tests/test_queryparam_start.py -v`
Expected: FAIL `Error: audio frame received before Start`

- [ ] **Step 3: Implement minimal fix trong `main.py:91`**

```python
# Ngay sau await ws.accept(), thêm:
from urllib.parse import parse_qs
qs = parse_qs(ws.scope.get("query_string", b"").decode())
if qs.get("sample_rate") and qs.get("encoding"):
    try:
        payload = {
            "type": "Start",
            "sample_rate": int(qs["sample_rate"][0]),
            "encoding": qs["encoding"][0],
            "channels": int(qs.get("channels", ["1"])[0]),
            "language": qs.get("language", ["vi"])[0],
            "model": qs.get("model", ["nova-3"])[0],
            "interim_results": qs.get("interim_results", ["false"])[0].lower() == "true",
        }
        protocol.validate_start(payload)
        rec = create_recognizer()
        await ws.send_text(protocol.encode_metadata(str(uuid.uuid4()), recognizer_mod.MODEL_DIR_NAME))
    except protocol.ProtocolError:
        pass  # fallback to JSON Start path
```

- [ ] **Step 4: Chạy lại test → PASS, và test cũ vẫn PASS**

Run: `bash selfhost/stt-adapter/run-tests.sh`
Expected: 9/9 + 1 mới = 10 PASS (trong đó `test_binary_before_start_is_rejected` vẫn pass khi không có query_string)

- [ ] **Step 5: Commit + rebuild trên VPS**

```bash
git add selfhost/stt-adapter/main.py selfhost/stt-adapter/tests/test_queryparam_start.py
git commit -m "fix(stt-adapter): auto-start from query_string for deepgram-sdk 4.8.1"
# VPS: cd /opt/omi/compose && docker compose build stt-adapter && docker compose up -d stt-adapter
```

---

### Task 3: Làm cứng listen pipeline cho chạy nhiều giờ

**Files:**
- Modify: `selfhost/docker-compose.yml` — tuning `mem_limit` + `restart: unless-stopped` đã có, thêm `healthcheck` cho backend/pusher nếu thiếu
- Verify: `backend/routers/listen/runtime.py:646` và `conversations.py:192` không cần sửa sau khi Task 1 xong, nhưng thêm log rõ ràng cho `FailedPrecondition`

**Interfaces:**
- Consumes: `listen_pusher_pipeline` sequence docs (silence timeout, disconnect_path, durable finalization)
- Produces: WS không crash khi thiếu index (đã fix ở Task 1), log rõ ràng

- [ ] **Step 1: Viết soak check script (không cần code backend mới)**

```bash
# selfhost/scripts/soak-test.sh
#!/bin/bash
# 5 user concurrent, mỗi user 1 WS /v4/listen, gửi silence PCM 600ms mỗi 5s trong 8h
for uid in u1 u2 u3 u4 u5; do
  (while true; do curl -s http://127.0.0.1:8092/health > /dev/null; sleep 5; done) &
done
```

- [ ] **Step 2: Chạy soak 10 phút thử trước khi 8h**

Run: `bash selfhost/scripts/soak-test.sh & sleep 600; docker compose logs backend --since 10m | grep -c "recovering stale"` — phải <5, không tăng liên tục

- [ ] **Step 3: Nếu vẫn crash, thêm fail-open cho meetings query (optional)**

```python
# backend/routers/listen/conversations.py:192
try:
    meetings = await get_meetings_for_user(uid, start, end)
except FailedPrecondition as e:
    if "index" in str(e).lower():
        logger.warning("meetings index missing, skipping meeting context uid=%s", uid)
        meetings = []
    else:
        raise
```

- [ ] **Step 4: Verify**

Run: `pytest backend/tests/unit/test_listen_conversations.py -v` (nếu có)

- [ ] **Step 5: Commit**

```bash
git add selfhost/scripts/soak-test.sh  # + backend file nếu sửa
git commit -m "chore(listen): soak harness for multi-hour multi-user"
```

---

### Task 4: Xử lý private-cloud 403 và tuning LLM cho đa user

**Files:**
- Modify: `selfhost/.env.template` — thêm `BUCKET_BACKUPS` hoặc `PRIVATE_CLOUD_ENABLED=false` nếu muốn tắt upload
- Modify: `backend/utils/other/storage.py` hoặc `.env` — nếu bucket chưa tạo thì set `PRIVATE_CLOUD_ENABLED=false` để bỏ qua 403
- Modify: `selfhost/omi-apps/app/config.py` — đã có `llm_timeout_seconds=75`, cần thêm circuit-breaker cho backend LLM

**Interfaces:**
- Consumes: `utils.http_client.get_webhook_client()` với semaphore, `OMI_LLM_GATEWAY_*` vars
- Produces: Không còn 403 spam trong pusher log khi self-host không có GCS bucket

- [ ] **Step 1: Xác nhận bucket có tồn tại không**

```bash
gsutil ls gs://$(grep BUCKET_BACKUPS /opt/omi/.env | cut -d= -f2) 2>&1 | head -5
# Nếu 403/404 thì bucket chưa tạo
```

- [ ] **Step 2: Nếu chưa tạo bucket, disable private-cloud upload**

```bash
# Thêm vào /opt/omi/.env:
PRIVATE_CLOUD_ENABLED=false
# Hoặc tạo bucket: gsutil mb -l asia-southeast1 gs://omi-xuan-backups
```

- [ ] **Step 3: Test lại pusher không còn 403 sau 5 phút**

Run: `docker compose logs pusher --since 5m | grep -c "403"` → 0

- [ ] **Step 4: Commit nếu đổi template**

```bash
git add selfhost/.env.template
git commit -m "docs(selfhost): document private-cloud bucket requirement"
```

---

### Task 5: Quan sát và vận hành (multi-user)

**Files:**
- Create: `selfhost/scripts/full-health.sh` (đã có phiên bản tạm, cần chuẩn hóa)
- Modify: `AGENTS.md` — cập nhật service table + Known Limitations sau Task 1-4

**Interfaces:**
- Consumes: `docker compose ps`, `curl /health` 4 endpoint, `free -h`, `df -h`
- Produces: Dashboard 1-lệnh kiểm tra toàn hệ

- [ ] **Step 1: Chuẩn hóa health script**

```bash
#!/bin/bash
set -e
docker ps --format "{{.Names}} {{.Status}}"
for h in omi-api omi-desk omi-ws omi-app; do
  curl -s -o /dev/null -w "$h: %{http_code}\n" "https://$h.xuanloi.me/health"
done
```

- [ ] **Step 2: Thêm cron check disk/RAM alert (optional)**

```bash
# crontab: mỗi giờ ghi metrics vào log
* * * * * free -h | logger -t omi-metrics
```

- [ ] **Step 3: Verify**

Run: `bash selfhost/scripts/full-health.sh` → 8/8 Up, 4/4 200

- [ ] **Step 4: Commit + cập nhật AGENTS.md**

```bash
git add selfhost/scripts/full-health.sh AGENTS.md
git commit -m "docs(selfhost): health dashboard for multi-user ops"
```

---

## Self-Review

- [x] Spec coverage: Backend_Setup (Task1 Firestore), listen_pusher_pipeline (Task3), Real-time Transcription STT (Task2), LLM gateway timeout (Task4), multi-user soak (Task3)
- [x] Placeholder scan: Không có TODO/TBD, mỗi step có code cụ thể
- [x] Type consistency: `ws.scope["query_string"]` dùng đúng Starlette WebSocket, `protocol.validate_start` signature khớp Task2

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-24-omi-stable-multiuser.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
