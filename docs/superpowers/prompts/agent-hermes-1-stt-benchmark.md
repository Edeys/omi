# Prompt cho Hermes Agent 1 — STT Benchmark Deploy & Real Voice

**Dán nguyên văn cho Hermes Agent 1 (máy/phiên riêng).**

Bạn phụ trách **Issue #9** (STT tiếng Việt) phần còn lại sau khi code benchmark đã merge.

**Context repo:**
- Nhánh: `feat/selfhost-backend` (worktree: `git worktree add C:\Omi\omi-h1 feat/selfhost-backend`)
- Báo cáo benchmark TTS đã merge: `docs/superpowers/reports/` — Deepgram nova-3 vi thắng (2.44% WER)
- File bench: `selfhost/scripts/stt_benchmark.py` (đã có, chạy trên VPS)
- Keys: `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY` đã nằm trong `/opt/omi/.env` (container backend đọc được sau restart)

**Việc của bạn (2 bước, ~1.5h):**

1. **Deploy routing theo kết quả benchmark:**
   - Đọc `backend/config/stt_provider_policy.py` + `STT_SERVICE_MODELS` env contract (backend/AGENTS.md)
   - Set trên VPS: `DEEPGRAM_SELF_HOSTED_ENABLED=false` (để cloud Nova-3 vi làm primary, sherpa local fallback)
   - **Phối hợp:** ping agent chính trước khi `docker compose build/up` (cùng VPS)
   - Verify: 1 phiên listen thật trên app → transcript tốt

2. **Bổ sung benchmark giọng thật:**
   - File anh đã gửi: `C:\Users\xuanl\OneDrive\Máy tính\26 thg 8 lúc 01-47_1.m4a` (đã trên VPS tại `/tmp/real-voice.m4a`, ref đã set)
   - Đã chạy 1 lần với placeholder ref → giờ chạy lại với ref đúng (nội dung thật: "Đây là giọng nói của anh...") để lấy WER giọng thật chính xác
   - Chạy: `cd /opt/omi && set -a; source /opt/omi/.env; set +a; python3 selfhost/scripts/stt_benchmark.py --samples-dir /tmp/bench-real --out /tmp/bench-real/results2.json`
   - Cập nhật report `docs/superpowers/reports/2026-08-25-stt-benchmark-results.md` thêm cột giọng thật
   - Commit: `docs(stt): add real-voice benchmark (giọng anh)`

**Báo cáo về agent chính:**
```
Hermes-1: benchmark real-voice WER: Deepgram vi X%, AssemblyAI Y%, local Z% — routing đã set false, verify listen OK
Commit: <hash>
```

**Không làm:** Đừng đụng `docs/superpowers/plans/2026-08-26-omi-hard-tasks.md` (của Antigravity), đừng tự tạo issue mới.
