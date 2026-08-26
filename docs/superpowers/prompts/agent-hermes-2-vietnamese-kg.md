# Prompt cho Hermes Agent 2 — Tiếng Việt Output + Onboarding KG 409

**Dán nguyên văn cho Hermes Agent 2.**

Bạn phụ trách **Issue #10** (2 phần, code đã merge nhưng cần verify E2E).

**Context:**
- Nhánh: `feat/selfhost-backend`
- Code đã merge: `OMI_FORCE_OUTPUT_LANGUAGE` helper (`process_conversation.py:291`, commit `60f2c4e526`), KG 409 fix (`94b38c4065` + `c12da642cf`)
- Env trên VPS: `OMI_FORCE_OUTPUT_LANGUAGE=vi` đã set (kiểm tra `grep OMI_FORCE /opt/omi/.env`), `DEEPGRAM_SELF_HOSTED_ENABLED=false` do Hermes-1 set

**Việc của bạn:**

1. **Verify tiếng Việt output (30 phút):**
   - Ghi 1 hội thoại mới bằng tiếng Việt trên app (điện thoại hoặc desktop)
   - Chờ 1-2 phút → kiểm tra Firestore/ app: title + tóm tắt phải bằng tiếng Việt (không phải tiếng Anh)
   - Nếu vẫn tiếng Anh → debug `process_conversation.py:291 _effective_output_language` (env đọc đúng chưa, helper được gọi chưa)
   - Ghi evidence vào comment Issue #10

2. **Verify onboarding KG không còn màn hình đỏ (1h):**
   - Trên app: logout → login lại → đi qua onboarding đến bước "Đây là những gì tôi biết về bạn" (knowledge graph)
   - Trước fix: báo `Failed to rebuild knowledge graph: Canonical...` (409). Sau fix: phải tự skip (trả `{skipped:true}`) → không hiện lỗi, bấm Tiếp tục được
   - Kiểm tra code: `app/lib/backend/http/api/knowledge_graph_api.dart:27` (bắt 409), `app/lib/pages/onboarding/wrapper.dart:161`
   - Nếu vẫn đỏ → đọc lại `app/lib/pages/onboarding/knowledge_graph_step.dart` và sửa theo spec trong plan `2026-08-25-omi-light-workloads.md` Task 3

3. **Build APK mới nếu cần (30 phút, chỉ khi fix thêm):**
   - `flutter build apk --flavor dev --release --dart-define=OMI_APP_PROFILE=selfhost`
   - Upload `/var/www/downloads/` trên VPS (đã có nginx `application/vnd.android.package-archive`)

**Báo cáo về agent chính:**
```
Hermes-2: vi-output PASS/FAIL (evidence: title "..."), KG onboarding PASS/FAIL (ảnh chụp màn hình)
Commit: <hash nếu có sửa>
```

**Không làm:** Đừng đụng STT benchmark (của H1) hay soak test (của H3/Antigravity).
