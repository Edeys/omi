# Prompt cho Agent Antigravity — Scale & Punctuation Realtime (Nặng)

**Dán nguyên văn cho agent Antigravity (worktree `C:\Omi\omi-antigravity` hoặc mới).**

Bạn xử lý 2 việc nặng còn tồn:

## Task A — Punctuation Realtime trong stt-adapter (tiếp nối Batch-2 T1)
- File: `selfhost/stt-adapter/main.py:91-148` đã có hook backend `punctuate_segments` (env-gated). Giờ thêm nhánh realtime:
  - Env mới: `OMI_PUNCTUATE_REALTIME` (default `false`)
  - Import `punctuate_text_realtime` từ `backend/utils/stt/punctuation_llm.py` (đã có helper) vào adapter, gọi trước `encode_results` khi `language` startswith `vi`.
  - Test: `backend/tests/unit/test_hard_punctuation_realtime.py` đã có 3 case — chạy `pytest` phải PASS.
  - Commit: `feat(stt): hybrid realtime vi punctuation (mimo-v2.5, env-gated, fail-open)`

## Task B — Scale Soak Real-Auth + Capacity Matrix
- File: `selfhost/scripts/soak-real-auth.py` (đã có bản nháp từ Hard Task 2)
- Hoàn thiện helper `mint_custom_token(uid)` + `SoakConfig`, CLI `--users 5 --duration 600 --ramp 60`
- Chạy thử ngắn `N=3/60s` rồi đủ `N=5/600s`, thu thập `docker compose logs backend --since 10m | grep -c "recovering stale"`, `free -h`, `docker stats`
- Điền `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md` bảng Users/RAM/CPU/Stale/Verdict
- **Constraint:** Ping agent chính trước khi `docker compose build/up` trên VPS (cùng VPS 103.116.39.65)

**Báo cáo về:** Commit hash + pytest evidence + bảng matrix

**Branch:** `feat/selfhost-backend`, push về `Edeys/omi-private`, worktree riêng.
