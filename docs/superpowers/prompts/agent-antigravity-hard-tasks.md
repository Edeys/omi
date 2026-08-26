# Prompt cho Agent Antigravity — 4 Việc Khó (Nặng)

**Dán nguyên văn prompt này cho agent Antigravity.**

---

Bạn là agent Antigravity phụ trách 4 việc khó của dự án Omi self-host. Làm việc **trực tiếp trên nhánh `feat/selfhost-backend`**, push về `Edeys/omi-private` (theo convention `18f1c33555`).

**Plan chi tiết:** `docs/superpowers/plans/2026-08-26-omi-hard-tasks.md` (458 dòng, đã có sẵn trong repo)
**Plan không cần plugin:** `docs/superpowers/plans/2026-08-26-omi-hard-tasks-antigravity.md` (bản Antigravity, không phụ thuộc superpowers)

**4 Task — làm tuần tự, mỗi Task 1 commit kèm evidence:**

1. **Hybrid STT + Realtime Vietnamese Punctuation** (`backend/utils/stt/punctuation_llm.py`)
   - Tạo helper `punctuate_text_realtime(text, language="vi") -> str`, env-gated `OMI_PUNCTUATE_REALTIME` (default false), fail-open
   - Test: `backend/tests/unit/test_hard_punctuation_realtime.py` (3 case đã ghi sẵn trong plan)
   - Wire vào `selfhost/stt-adapter/main.py` vòng `for segment in segments:` trước `encode_results` (behind env)

2. **Real-Auth Soak + Capacity Matrix** (`selfhost/scripts/soak-real-auth.py`)
   - Helper `mint_custom_token(uid)` + dataclass `SoakConfig`, CLI `--users 5 --duration 600 --ramp 60`
   - Test: `backend/tests/unit/test_hard_scale_soak.py` (2 case)
   - Dry-run N=3/60s, sau đó 5/600s thu thập `recovering stale` count, `free -h`, `docker stats` → điền `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md`

3. **Speech-Profile Bucket Probe (billing-gated)** (`backend/utils/other/storage.py`)
   - Thêm `ensure_speech_profile_bucket(uid) -> bool` gần `_get_speech_profiles_bucket`
   - Test: `backend/tests/unit/test_hard_speech_profile.py` (2 case)

4. **ADB Logcat Harness** (`tools/adb_logcat.py`, `tools/check-adb-device.sh`)
   - Thay simulator bằng log thật từ Pixel 4 (`C:\Omi\toolchain\android-sdk\platform-tools\adb.exe`)
   - Test: `tests/unit/test_adb_logcat.py` (2 case)

**Global Constraints:**
- Python 3.11, `black --line-length 120 --skip-string-normalization`
- Worktree riêng: `git worktree add C:\Omi\omi-hard feat/selfhost-backend` (KHÔNG đụng `main`)
- **KHÔNG tự `docker compose build/up` trên VPS khi agent chính đang deploy** — ping trước
- TDD: viết test FAIL → chạy → implement → PASS → commit

**Khi xong mỗi Task:** push 1 commit, comment vào Issue tương ứng (nếu có), và ghi vào `docs/superpowers/reports/` nếu là Task 2.

**Báo cáo cuối:** reply cho agent chính (em) theo mẫu:
```
Task X: <tên> — PASS/FAIL
Commit: <hash>
Evidence: pytest <path> -v (X passed)
VPS deploy: cần/không, đã ping agent chính chưa
```

**Lưu ý quan trọng:**
- Task 1 phụ thuộc Batch-2 Task 1 (`punctuate_segments` batch) — nếu chưa merge, đọc `backend/utils/conversations/punctuation.py` trước
- Task 2 cần Firebase SA (`/opt/omi/secrets/...`) — hỏi agent chính nếu thiếu quyền đọc .env
