# Prompt cho Hermes Agent 2 — Docs Sync + APK Public URL Verify

**Dán nguyên văn cho Hermes Agent 2.**

Bạn phụ trách **đồng bộ tài liệu** và **verify APK public**.

**Việc (1h):**

1. **Docs sync:**
   - Mở `AGENTS.md` fork section, kiểm tra bảng Service có dòng `OMI_EMBEDDINGS_*` (3 biến) + `OMI_PUNCTUATE_ENABLED` + `mimo-v2.5` + `n8n stopped` + Modal routine chưa — nếu thiếu, bổ sung theo commit `3bfed95f4c` làm mẫu
   - Kiểm tra `selfhost/.env.template` có block `OMI_EMBEDDINGS_*` và `OMI_PUNCTUATE_ENABLED=true` chưa
   - Fix nếu thiếu, `black` nếu sửa Python, commit `docs(selfhost): sync ...`

2. **APK public URL verify:**
   - `curl -sI https://omi-api.xuanloi.me/downloads/omi-selfhost-dev.apk | grep -iE 'HTTP|content-type|disposition|content-length'`
   - Phải ra `200`, `application/vnd.android.package-archive`, `Content-Disposition: attachment`, `Content-Length: 192479059`
   - Nếu 404 → kiểm tra `grep -n downloads /etc/nginx/sites-available/omi-api` phải nằm trong block `listen 443`, không phải block 80 (lỗi cũ đã fix)

3. **Báo cáo:** Comment vào Issue liên quan hoặc reply cho agent chính.

**Branch:** `feat/selfhost-backend`, worktree riêng, push về `Edeys/omi-private`.
