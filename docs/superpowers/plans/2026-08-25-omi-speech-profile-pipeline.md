# Speech Profile + Audio Storage Pipeline (ready-on-billing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.
> Nhãn [A] = agent, [U] = user. **TRIGGER: plan này chỉ thực thi khi user đã
> gắn billing account cho GCP project `omi-xuan`.**

**Goal:** Bật speech profile (nhận diện giọng chủ nhân) + audio storage/playback
+ private cloud sync — 3 tính năng đang bị chặn vì không có bucket GCS.

**Architecture:** Dùng script provision có sẵn (`selfhost/scripts/provision-buckets.sh`,
8 bucket, region asia-southeast1, grant objectAdmin cho firebase-adminsdk SA).
Không đổi code — chỉ cấp tài nguyên + env (mọi code path đã verify: storage.py
đọc env lúc import, fail-soft khi thiếu).

**Tech Stack:** gcloud/gsutil (hoặc script python qua backend container như lần
meetings index), Docker Compose.

**Spec:** `selfhost/scripts/provision-buckets.sh` + `backend/utils/other/storage.py:82-90`
+ plan docs-parity Task 2 (đã commit) + AGENTS.md fork section.

## Global Constraints

- Bucket names khớp CHÍNH XÁC env mà `storage.py:82-90` đọc
- Secrets/env không commit; `/opt/omi/.env` mode 600
- Sau khi set env mới: bắt buộc `docker compose up -d` recreate (env đọc lúc import)
- Nhãn [A] = agent, [U] = user

---

### Task 1: Tạo 8 bucket + grant IAM [U + A]

- [ ] **Step 1 [U]:** Gắn billing: https://console.cloud.google.com/billing →
      Create/choose account → **My projects → omi-xuan → Change billing** 
- [ ] **Step 2 [A]:** Chạy provision (2 đường):
      - Nếu VPS có gcloud: `bash /opt/omi/selfhost/scripts/provision-buckets.sh`
      - Nếu không: script python qua backend container (pattern như lần meetings
        index — `storage.Client.create_bucket(name, location='asia-southeast1')`
        + set_iam_policy objectAdmin cho firebase-adminsdk SA)
- [ ] **Step 3 [A]:** Verify: `gsutil ls` (hoặc python list_buckets) thấy đủ 8 bucket
- [ ] **Step 4 [A]:** Commit (chỉ nếu sửa script) — không commit key

### Task 2: Cập nhật env + restart [A]

- [ ] **Step 1 [A]:** `/opt/omi/.env` — set các value (đã có dòng trống từ trước):
```
BUCKET_PRIVATE_CLOUD_SYNC=omi-private-cloud-sync
BUCKET_SPEECH_PROFILES=omi-speech-profiles
BUCKET_MEMORIES_RECORDINGS=omi-memories-recordings
BUCKET_POSTPROCESSING=omi-postprocessing
BUCKET_TEMPORAL_SYNC_LOCAL=omi-temporal-sync-local
BUCKET_CHAT_FILES=omi-chat-files
BUCKET_APP_THUMBNAILS=omi-app-thumbnails
BUCKET_PLUGINS_LOGOS=omi-plugins-logos
```
      + bật lại `private_cloud_sync_enabled=true` cho user (Firestore, đã tắt
        từ 2026-08-25 để chặn 403 spam)
- [ ] **Step 2 [A]:** `cd /opt/omi/compose && docker compose up -d` (recreate để env vào)
- [ ] **Step 3 [A]:** Verify: log backend KHÔNG còn "BUCKET_SPEECH_PROFILES is
      not configured"; pusher 5 phút không còn 403

### Task 3: E2E speech profile + speaker-ID [U + A]

- [ ] **Step 1 [U]:** App → tạo speech profile (đọc đoạn văn 20-30s)
- [ ] **Step 2 [A]:** Verify: `GET /v3/speech-profile` trả profile; bucket có
        object `{uid}/speech_profile.wav`
- [ ] **Step 3 [U+A]:** Ghi 1 hội thoại → segments có `is_user=true` đúng
        (speaker identification hoạt động qua Modal VAD + speech profile)
- [ ] **Step 4 [U]:** Mở conversation có audio → nghe playback được
- [ ] **Step 5 [A]:** Cập nhật AGENTS.md: gỡ Known Limitation "speech profile
        storage disabled" + commit

---

## Self-Review

- [x] Mọi bucket name khớp `storage.py:82-90`; region khớp Firestore
      (asia-southeast1); SA đã có quyền theo script provision
- [x] Trigger rõ ràng: billing; các bước sau đó không cần user quyết thêm

## Execution Handoff

Inline. Task 1 Step 1 là [U] — user gắn billing là cờ khởi động duy nhất.
