# Omi Self-Host Docs-Parity Bugfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa toàn bộ lỗi đang treo (Firestore meetings index, 403 audio chunks) và lấp
khoảng trống tính năng giữa docs.omi.me với hệ thống self-host trên VPS 103.116.39.65
(project Firebase `omi-xuan`): vector search thay thế local, buckets lưu trữ đầy đủ,
vận hành đa user ổn định.

**Architecture:** Giữ nguyên Docker Compose 3-tier (backend/desktop-backend/pusher +
redis/stt-adapter/omi-apps/notifications-job) — không thêm container mới. Vector search
thay Pinecone bằng module nhúng SQLite+numpy đặt sau cùng một handle interface trong
`database/vector_db.py`. GCS buckets provision bằng script idempotent. Firestore index
đi đúng pipeline registry → generate → manifest → deploy của repo.

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLite (WAL) + numpy, gcloud/firebase CLI,
Docker Compose, nginx + Let's Encrypt (đã có).

**Spec:** docs.omi.me (Backend_Setup, Real-time Transcription, Chat System,
Storing Conversations, ChatTools) + `AGENTS.md` fork section + kết quả đối chiếu
docs-vs-code ngày 2026-08-24 (mọi mục đều đã verify vào code kèm file:line).

## Quyết định đã chốt với user (2026-08-24)

| Vấn đề | Quyết định |
|---|---|
| Batch STT / voice messages fail closed | **Chưa làm** — ghi Known Limitation (Task 5) |
| Vector search thiếu Pinecone | **Làm thay thế local** (Task 3) |
| Apple OAuth | **Không cần** — ghi Known Limitation (Task 5) |
| Tạo 7 GCS buckets trên omi-xuan | **OK** (Task 2) |

## Global Constraints

- Python 3.11 only (`backend/AGENTS.md`); `python:3.11-slim` trong Dockerfile
- Format: `black --line-length 120 --skip-string-normalization`
- Secrets không commit: `/opt/omi/.env` mode 600; `/opt/omi/secrets/firebase-service-account.json`
- Firestore index là nguồn sự thật `backend/database/firestore_index_registry.py`;
  tạo index chỉ qua `generate_firestore_indexes.py` → `firestore.indexes.json`;
  CẤM `gcloud firestore indexes composite create` lẻ tẻ
- Không đụng `main`; làm trên `feat/selfhost-backend`; mỗi task 1 commit, message
  ghi rõ evidence lệnh đã chạy
- TDD: test mới phải FAIL trước khi implement, PASS sau; test hermetic
  (không network, không live service)
- Logging không in raw PII (`utils.log_sanitizer`); fallback mới gọi `record_fallback`
- Mỗi bước có dán nhãn [A] = agent làm, [U] = user thao tác tay

---

## File Structure

**Sửa:**
- `backend/database/firestore_index_registry.py` — thêm requirement meetings-overlap
- `firestore.indexes.json` — regenerate từ registry (không edit tay)
- `selfhost/.env.template` — hoàn thiện bucket vars, xoá biến chết, hết drift base URL
- `backend/database/vector_db.py:91-102` — thêm nhánh fallback LocalVectorIndex
- `selfhost/docker-compose.yml` — healthchecks + volume vector_data
- `AGENTS.md` — Known Limitations + service table đồng bộ thực tế

**Tạo:**
- `backend/tests/unit/test_firestore_indexes_meetings.py`
- `selfhost/scripts/provision-buckets.sh`
- `backend/database/local_vector_index.py`
- `backend/tests/unit/test_local_vector_index.py`
- `selfhost/scripts/full-health.sh`
- `selfhost/scripts/soak-test.sh`

---

### Task 1: Composite index `meetings` — fix FailedPrecondition crash trong listen pipeline

**Bối cảnh (evidence):** Query `start_time < end AND end_time > start ORDER BY start_time`
tại `backend/database/calendar_meetings.py:170-173` cần composite index
(start_time ASC, end_time ASC) — chính file này ghi chú điều đó. Query chạy mỗi lần
desktop tạo conversation (`routers/listen/conversations.py:257-264`). Manifest hiện tại
39 index nhưng KHÔNG có meetings; registry cũng chưa khai báo spec → phải thêm spec
trước rồi mới generate.

**Files:**
- Modify: `backend/database/firestore_index_registry.py`
- Modify: `firestore.indexes.json` (generated)
- Create: `backend/tests/unit/test_firestore_indexes_meetings.py`

**Interfaces:**
- Consumes: `FirestoreIndexRequirement`, `FirestoreIndexField` (registry.py:15-49),
  script `backend/scripts/generate_firestore_indexes.py --write`,
  `backend/scripts/reconcile_firestore_indexes.py --check-only`
- Produces: manifest chứa composite `(meetings: start_time ASC, end_time ASC)`

- [ ] **Step 1 [A]:** Grep entry mẫu trong registry để copy CHÍNH XÁC convention
      `identifier` + `query_scope` của repo.
- [ ] **Step 2 [A]:** Viết test FAIL (test đọc manifest, assert composite meetings).
- [ ] **Step 3 [A]:** Run pytest → FAIL "meetings overlap composite missing".
- [ ] **Step 4 [A]:** Thêm requirement vào registry; generate lại manifest;
      git diff thấy meetings; test PASS; reconcile check-only.
- [ ] **Step 5 [A]:** Commit `fix(firestore): declare meetings overlap composite index`.
- [ ] **Step 6 [U]:** Deploy index: `firebase deploy --only firestore:indexes
      --project=omi-xuan` hoặc click link create-index trong log backend;
      đợi Enabled; verify phiên desktop listen hết FailedPrecondition.

### Task 2: Provision 7 GCS buckets + hoàn thiện .env.template

**Bối cảnh (evidence):** `storage.py:85` dùng bucket mặc định `'omi-private-cloud-sync'`
(không tồn tại trong project) → upload audio chunk 403. `storage.py:82-90` đọc các env
bucket. Template hiện chỉ có 3 bucket. `BUCKET_BACKUPS` là biến CHẾT (grep = 0 caller).
Speech profile raise RuntimeError khi bucket trống (`storage.py:124`).

**Files:**
- Create: `selfhost/scripts/provision-buckets.sh`
- Modify: `selfhost/.env.template`

- [ ] **Step 1 [A]:** Viết script idempotent tạo 7 bucket + grant objectAdmin cho SA.
- [ ] **Step 2 [A]:** `.env.template`: section Storage đầy đủ; xoá BUCKET_BACKUPS.
- [ ] **Step 3 [A]:** Hết drift OPENAI_BASE_URL (kiểm tra giá trị thật trên VPS).
- [ ] **Step 4 [U]:** Chạy script; điền value vào `/opt/omi/.env`; restart compose.
- [ ] **Step 5 [U]:** Verify pusher log không còn 403; tạo speech profile OK.
- [ ] **Step 6 [A]:** Commit `feat(selfhost): provision 7 storage buckets + finalize env template`.

### Task 3: LocalVectorIndex — thay Pinecone bằng vector store nhúng SQLite+numpy

**Bối cảnh (evidence):** `PINECONE_*` trống → `index=None` (`vector_db.py:100-102`) →
`query_vectors` trả `[]` → chat mất tìm-theo-chủ đề. Toàn bộ lời gọi Pinecone đi qua
1 handle `index` duy nhất với 5 method upsert/query/update/delete/list (grep đủ).
Embeddings chạy qua OpenAI-compatible proxy sẵn có (`utils/llm/clients.py`) — không đổi.

**Files:**
- Create: `backend/database/local_vector_index.py`
- Modify: `backend/database/vector_db.py:91-102`
- Modify: `selfhost/docker-compose.yml` (volume vector_data cho backend,
  desktop-backend, pusher, notifications-job)
- Modify: `selfhost/.env.template` (LOCAL_VECTOR_ENABLED, LOCAL_VECTOR_DB_PATH)
- Test: `backend/tests/unit/test_local_vector_index.py`

**Interfaces — LocalVectorIndex implement đúng subset Pinecone được dùng:**
- `upsert(vectors=[{id, values, metadata}], namespace)`
- `query(vector, top_k, include_metadata, filter, namespace)` → `res["matches"]` =
  list `{id, score, metadata?}`
- `update(id, set_metadata, namespace)`
- `delete(ids=[...], namespace)` và `delete(filter=dict, namespace)`
- `list(prefix, namespace)` → iterable pages, mỗi page list id ≤100
- Filter operators: `$eq`, `$in`, `$gte`, `$lte`, `$and`, `$or` (grep thêm
  `memory_vector_metadata.py` để chắc không sót)

- [ ] **Step 1 [A]:** Viết test FAIL (hermetic tmp_path).
- [ ] **Step 2 [A]:** Implement LocalVectorIndex (SQLite WAL, numpy cosine, cache).
- [ ] **Step 3 [A]:** Integration test monkeypatch `vector_db.index` → query_vectors PASS.
- [ ] **Step 4 [A]:** Wire fallback vào vector_db.py khi LOCAL_VECTOR_ENABLED=true.
- [ ] **Step 5 [A]:** Compose volume + env template vars.
- [ ] **Step 6 [A]:** Full suite `-k "vector or rag"` PASS + black format.
- [ ] **Step 7 [A]:** Commit `feat(vector): embedded sqlite-numpy LocalVectorIndex replaces Pinecone`.
- [ ] **Step 8 [U]:** Deploy VPS; test chat theo chủ đề có citation.

### Task 4: Compose healthchecks + scripts vận hành multi-user

**Files:**
- Modify: `selfhost/docker-compose.yml`
- Create: `selfhost/scripts/full-health.sh`
- Create: `selfhost/scripts/soak-test.sh`

- [ ] **Step 1 [A]:** Healthcheck python stdlib cho 7 service; redis-cli ping cho redis.
- [ ] **Step 2 [A]:** full-health.sh: docker ps + curl 4 domain /health, exit≠0 nếu fail.
- [ ] **Step 3 [A]:** soak-test.sh: DURATION/N luồng, đếm "recovering stale" < 5.
- [ ] **Step 4 [A]:** bash -n PASS; commit `chore(selfhost): compose healthchecks + ops scripts`.
- [ ] **Step 5 [U]:** Deploy; chạy full-health.sh → 8/8 Up, 4/4 HTTP 200.

### Task 5: Đồng bộ tài liệu với thực tế đã deploy

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1 [A]:** Known Limitations: batch STT fail closed có chủ ý
      (`pre_recorded.py:139-148`); Apple OAuth tắt; Pinecone → LocalVectorIndex;
      liệt kê 7 bucket đã provision.
- [ ] **Step 2 [A]:** Service table env mới; OPENAI_BASE_URL giá trị thật; evidence verify.
- [ ] **Step 3 [A]:** Commit `docs(selfhost): sync AGENTS.md with deployed reality`.

---

## Self-Review (đã chạy lúc lập plan)

- [x] Spec coverage: meetings index (T1), 403+speech profile+buckets (T2), vector search (T3),
      vận hành (T4), doc drift + limitations + quyết định batch-STT/Apple-OAuth (T5).
- [x] Placeholder scan: các bước có code/lệnh cụ thể; chỗ "copy convention mẫu" là thao tác
      đọc-làm-theo có chỉ dẫn grep chính xác.
- [x] Type consistency: surface LocalVectorIndex khớp 100% cách gọi trong vector_db.py;
      env names khớp chuỗi storage.py:82-90 đọc.
- [x] Sai lầm plan cũ đã loại bỏ: registry thiếu spec meetings (thêm spec trước khi generate);
      PRIVATE_CLOUD_ENABLED không tồn tại; BUCKET_BACKUPS biến chết — bucket gây 403 thật là
      BUCKET_PRIVATE_CLOUD_SYNC.

## Execution Handoff

Chạy Subagent-Driven hoặc Inline; các bước [U] dừng giao lại cho user thao tác.
