# Prompt cho Hermes Agent 1 — Deploy & Verify STT Routing (Deepgram vi)

**Dán nguyên văn cho Hermes Agent 1.**

Bạn phụ trách **verify deploy** sau khi benchmark đã chốt winner.

**Context:**
- Benchmark giọng thật (18.5s, ref đúng Xuân Lợi): **AssemblyAI Universal WER 2.44%** thắng, **Deepgram Nova-3 vi 4.88%** hạng 2, `multi` 100% sai, sherpa 12.2% — đã commit `ce65e490f3`
- Env quyết định: `DEEPGRAM_SELF_HOSTED_ENABLED=false` (để Cloud Nova-3 vi làm primary, sherpa fallback). Env này đã set trên VPS (`grep -E` ra `false`), nhưng image backend cũ (8h trước) chưa chứa code Batch-2.

**Việc (45 phút):**
1. Xác nhận VPS đã pull `a39a6ef733` (chứa real-voice benchmark) — nếu chưa: `cd /opt/omi && git pull --ff-only`
2. Kiểm tra `grep -E '^OMI_PUNCT|DEEPGRAM_SELF' /opt/omi/.env` phải ra `true`/`false`/`vi` đúng
3. Nếu image backend cũ (Up >1h), báo agent chính để rebuild (đừng tự build khi disk 89% — cần prune trước)
4. Test 1 phiên listen thật trên app (điện thoại) → transcript phải có dấu, không ra `project你`
5. Comment vào Issue #9: "Verify deploy: routing Nova-3 vi OK, transcript mẫu: ..."

**Không làm:** Đừng đụng code STT, chỉ verify.

**Branch:** `feat/selfhost-backend` (worktree `C:\Omi\omi-h1` nếu còn, không thì tạo mới)
