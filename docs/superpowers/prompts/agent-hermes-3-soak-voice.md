# Prompt cho Hermes Agent 3 — Soak Test Real-Auth + Voice Messages Proposal

**Dán nguyên văn cho Hermes Agent 3.**

Bạn phụ trách 2 việc nhẹ còn lại:

**A. Soak Test Real-Auth (thuộc Batch-2 Task 3, đã code xong nhưng chưa chạy trên VPS)**

*Context:* File `selfhost/scripts/soak-real-auth.py` + `selfhost/scripts/SOAK-HARMONIZATION.md` đã merge (d78e66c07c). Agent Antigravity cũng có bản song song (`soak_real_auth.py`) — đã ghi harmonization, không xóa file của nhau, sẽ gộp sau.

*Việc:*
1. Đọc `selfhost/scripts/SOAK-HARMONIZATION.md` để hiểu 2 bản
2. Chạy soak ngắn trên VPS (phối hợp agent chính trước khi chạy vì tốn CPU/RAM):
   ```
   python selfhost/scripts/soak-real-auth.py --users 3 --duration 300 --ramp 30
   ```
   Pass nếu 0 WS crash và `recovering stale < 5` (đọc `docker compose logs backend --since 10m | grep -c "recovering stale"`)

3. Comment kết quả vào Issue #9 hoặc #10 (soak liên quan benchmark)

**B. Voice Messages Proposal Review (Issue #6 → plan 2026-08-26-omi-voice-messages-proposal.md)**

*Context:* Plan này agent PC-light đã viết proposal (commit d3572a53a9) — chờ agent chính duyệt, không tự code.

*Việc:*
1. Đọc `docs/superpowers/plans/2026-08-26-omi-voice-messages-proposal.md`
2. Review theo checklist trong proposal: có đủ spec coverage, placeholder scan, type consistency không?
3. Comment vào Issue #6: "Review: PASS/FAIL — <ghi chú>" (không tự implement, chỉ review)

**Báo cáo về agent chính:**
```
Hermes-3: soak 3/300 PASS (stale=2, RAM peak 2.1G), voice-messages proposal review PASS
Commit: <hash nếu có>
```

**Lưu ý:** Mọi restart VPS phải ping agent chính trước. Push về `Edeys/omi-private`.
