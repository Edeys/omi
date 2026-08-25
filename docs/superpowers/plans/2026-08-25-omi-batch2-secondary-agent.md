# Omi Self-Host — Secondary Agent Batch 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.
> Steps dùng checkbox (`- [ ]`). Nhãn [A] = agent làm, [U] = user làm.
> ⚠️ Nếu plan `2026-08-25-omi-light-workloads.md` (T1-T3) CHƯA làm thì làm plan đó
> TRƯỚC — Batch 2 này không phụ thuộc T1-T3 nhưng ưu tiên thấp hơn.

**Goal:** (1) Thêm dấu câu tiếng Việt cho transcript (hiện pass-through không dấu
— khó đọc), (2) đồng bộ docs/env với thực tế deploy, (3) soak test đa user với
auth thật để chứng minh scale-ready.

**Architecture:** Punctuation = post-processing LLM (mimo-v2.5 qua provider seam
có sẵn) chạy 1 lần lúc conversation finalization, trước khi lưu segments; env-gated
`OMI_PUNCTUATE_ENABLED`. Không đụng đường streaming realtime.

**Tech Stack:** Python 3.11, pytest, OpenAI-compatible LLM (mimo-v2.5 qua zen).

**Spec:** GitHub Issues Edeys/omi + report `2026-08-25-stt-cloud-keys-setup.md`
(mục "Punctuation tiếng Việt: hiện stt-adapter chỉ pass-through") + AGENTS.md.

## Global Constraints

- Worktree từ nhánh `feat/selfhost-backend`; work repo push về `Edeys/omi-private`
  (theo convention commit `18f1c33555`); KHÔNG push sang public fork `Edeys/omi`
- Python 3.11; `black --line-length 120 --skip-string-normalization`; TDD fail-first
- LLM call phải async-safe + có timeout (dùng seam `get_llm`/providers có sẵn,
  KHÔNG tạo client mới); logging không in raw transcript (dùng `log_sanitizer`)
- ⚠️ Phối hợp với agent chính trước mọi `docker compose build/up` trên VPS
- Mỗi task 1 commit kèm evidence; nhãn [A] = agent, [U] = user

---

### Task 1: Punctuation tiếng Việt cho transcript lưu trữ

**Bối cảnh (đã verify):** stt-adapter chỉ pass-through text không dấu câu
(report f803728f16 mục 4). Segments được lưu lúc finalization qua
`lifecycle_service.persist_processed_conversation` trong
`utils/conversations/process_conversation.py` (tìm call site bằng
`grep -n 'persist_processed_conversation' backend/utils/conversations/process_conversation.py`).

**Files:**
- Create: `backend/utils/conversations/punctuation.py`
- Modify: `backend/utils/conversations/process_conversation.py` (gọi tại finalization)
- Modify: `selfhost/.env.template` + `/opt/omi/.env` (env mới, [U] phần .env)
- Test: `backend/tests/unit/test_punctuation.py`

**Interfaces:**
- Consumes: `providers.get_or_create_openai_compatible_llm('openai', model)` —
  client đã có shim `SelfHostStructuredChatOpenAI` (zen compat); env
  `OMI_PUNCTUATE_ENABLED` (mặc định false), `OMI_LIGHT_MODEL` (đang = mimo-v2.5)
- Produces: `punctuate_segments(uid: str, segments: List[TranscriptSegment]) -> List[TranscriptSegment]`
  — trả segments mới với `text` có dấu câu; lỗi LLM → trả nguyên danh sách gốc
  (fail-open, bắt buộc: không được làm hỏng conversation khi provider chết)

- [ ] **Step 1 [A]:** Viết test FAIL:
```python
"""Punctuation post-processing: ghép các segment text thành 1 khối, gửi LLM
để chèn dấu câu, rồi tách lại theo số segment gốc (1:1 mapping bắt buộc)."""
from unittest.mock import MagicMock, patch


def test_punctuate_joined_text_and_maps_back():
    segs = [_seg('xin chào bạn'), _seg('tôi là nam')]
    llm = MagicMock()
    llm.invoke.return_value = 'Xin chào bạn. Tôi là Nam.'
    with patch('utils.conversations.punctuation._get_llm', return_value=llm):
        from utils.conversations.punctuation import punctuate_segments
        out = punctuate_segments('uid', segs)
    assert [s.text for s in out] == ['Xin chào bạn.', 'Tôi là Nam.']


def test_fail_open_returns_original_on_llm_error():
    segs = [_seg('không dấu')]
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError('provider down')
    with patch('utils.conversations.punctuation._get_llm', return_value=llm):
        from utils.conversations.punctuation import punctuate_segments
        out = punctuate_segments('uid', segs)
    assert [s.text for s in out] == ['không dấu']


def test_disabled_env_returns_original(monkeypatch):
    monkeypatch.setenv('OMI_PUNCTUATE_ENABLED', 'false')
    segs = [_seg('gốc')]
    with patch('utils.conversations.punctuation._get_llm') as m:
        from utils.conversations.punctuation import punctuate_segments
        out = punctuate_segments('uid', segs)
    m.assert_not_called()
    assert out[0].text == 'gốc'


def _seg(text):
    from models.transcript_segment import TranscriptSegment
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    return TranscriptSegment(
        text=text, speaker='SPEAKER_0', is_user=True, person_id=None,
        start=0.0, end=1.0, created_at=now,
    )
```
      Run: `pytest backend/tests/unit/test_punctuation.py -v` → FAIL (module chưa có)
- [ ] **Step 2 [A]:** Implement `backend/utils/conversations/punctuation.py`:
```python
"""LLM punctuation cho transcript tiếng Việt lúc finalization.

Env OMI_PUNCTUATE_ENABLED=true để bật. Fail-open: mọi lỗi LLM trả nguyên
segments gốc — punctuation là enhancement, không được phá pipeline.
Prompt yêu cầu LLM trả về CÙNG SỐ dòng, mỗi dòng = 1 segment đã có dấu.
"""
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

_PROMPT = (
    'Bạn là bộ chèn dấu câu cho bản ghi hội thoại tiếng Việt. '
    'Dưới đây là {n} dòng, mỗi dòng là 1 đoạn hội thoại. '
    'Hãy viết lại CHÍNH XÁC từng dòng, chỉ THÊM dấu câu (.,?!...) và viết hoa '
    'chữ cái đầu nếu cần. KHÔNG đổi từ, KHÔNG thêm/xóa/dịch nội dung, '
    'KHÔNG thêm giải thích. Trả về đúng {n} dòng, mỗi dòng 1 đoạn.\n\n'
)


def _get_llm():
    from utils.llm.providers import get_or_create_openai_compatible_llm
    model = os.getenv('OMI_LIGHT_MODEL', 'mimo-v2.5')
    return get_or_create_openai_compatible_llm('openai', model)


def punctuate_segments(uid: str, segments: List) -> List:
    if os.getenv('OMI_PUNCTUATE_ENABLED', '').strip().lower() != 'true':
        return segments
    texts = [s.text for s in segments]
    if not any(t.strip() for t in texts):
        return segments
    prompt = _PROMPT.format(n=len(texts)) + '\n'.join(texts)
    try:
        llm = _get_llm()
        response = llm.invoke(prompt)
        lines = [ln for ln in str(response.content).splitlines() if ln.strip()]
        if len(lines) != len(texts):
            logger.warning('punctuate: line count mismatch %d != %d, skip', len(lines), len(texts))
            return segments
        out = []
        for seg, new_text in zip(segments, lines):
            out.append(seg.model_copy(update={'text': new_text}))
        logger.info('punctuate: updated %d segments uid=%s', len(out), uid)
        return out
    except Exception as e:
        logger.warning('punctuate failed uid=%s: %s', uid, e)
        return segments
```
      Lưu ý: nếu `TranscriptSegment` là pydantic BaseModel thì `model_copy` OK;
      nếu dataclass thì dùng `dataclasses.replace` — kiểm tra models/transcript_segment.py
- [ ] **Step 3 [A]:** Wire vào finalization — trong process_conversation.py, tìm
      chỗ gọi `persist_processed_conversation` (trước khi lưu), chèn:
```python
from utils.conversations.punctuation import punctuate_segments
if conversation.transcript_segments:
    conversation.transcript_segments = punctuate_segments(
        uid, conversation.transcript_segments)
```
      (chỉ nhánh KHÔNG deferred — deferred sẽ có punctuation khi enrich)
      Chèn SAU khi structured extraction thành công, TRƯỚC persist.
- [ ] **Step 4 [A]:** Test → PASS; `black` format; chạy lại
      `pytest backend/tests/unit/test_punctuation.py test_lazy_conversation_processing.py -q`
- [ ] **Step 5 [A]:** `.env.template` thêm:
```
# --- Punctuation tiếng Việt cho transcript lưu trữ ---
OMI_PUNCTUATE_ENABLED=true
```
      Commit `feat(selfhost): llm punctuation for stored transcripts (env-gated, fail-open)`
- [ ] **Step 6 [A]:** Deploy (đồng bộ agent chính): pull + `docker compose build backend` + up;
      set `OMI_PUNCTUATE_ENABLED=true` vào `/opt/omi/.env`
- [ ] **Step 7 [U]:** Ghi 1 hội thoại mới → mở conversation → transcript phải có
      dấu câu. Verify thêm: Firestore segments có dấu.

### Task 2: Đồng bộ docs/env với thực tế deploy

**Files:**
- Modify: `AGENTS.md` (fork section: Known Limitations + service table)
- Modify: `selfhost/.env.template`

- [ ] **Step 1 [A]:** AGENTS.md cập nhật:
  - Service table thêm: LLM `mimo-v2.5` (OMI_MAIN_MODEL + OMI_LIGHT_MODEL);
    Embeddings `gemini-embedding-001` qua `OMI_EMBEDDINGS_*` (zen không có
    /v1/embeddings); n8n ĐÃ DỪNG (data volume giữ, restore = `docker compose up -d n8n`
    từ `/opt/n8n`); Modal routine start/stop theo nhu cầu billing
  - Known Limitations thêm: punctuation qua LLM post-processing
    (OMI_PUNCTUATE_ENABLED), batch STT fail-closed (đã có)
- [ ] **Step 2 [A]:** `.env.template` thêm block `OMI_EMBEDDINGS_*` (3 biến,
  copy từ `/opt/omi/.env` dòng 96-98) + `OMI_PUNCTUATE_ENABLED=true`
- [ ] **Step 3 [A]:** Commit `docs(selfhost): sync env reference + service table`
- [ ] **Step 4 [U]:** Review nhanh phần AGENTS.md được sửa

### Task 3: Soak test đa user với auth thật

**Files:**
- Create: `selfhost/scripts/soak-real-auth.py`
- Modify: `selfhost/scripts/soak-test.sh` (gọi script python thay vì health-only)

**Interfaces:**
- Consumes: Firebase Admin SDK (backend container có SA) → `auth.create_custom_token(uid)`
  → exchange lấy ID token qua REST `identitytoolkit`; WS endpoint `/v4/listen`
- Produces: script chạy `N` phiên WS song song `DURATION` giây, assert
  không crash + đếm "recovering stale" < 5 (thay thế soak health-only cũ)

- [ ] **Step 1 [A]:** Viết `soak-real-auth.py` chạy TRONG backend container:
```python
# 1. create_custom_token(uid) qua firebase_admin.auth (SA đã mount)
# 2. sign-in custom token qua REST:
#    POST https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=$FIREBASE_API_KEY
#    -> idToken
# 3. websockets.connect(f'wss://omi-ws.../v4/listen?...&uid={uid}',
#        extra_headers={'Authorization': f'Bearer {idToken}'})
#    gửi silence PCM16 600ms mỗi 5s trong DURATION
# 4. N phiên song song (asyncio.gather), log mọi disconnect/error
```
      (chi tiết wire format opcode 100-105 xem `routers/listen/parity_pack_export.py`
      + docs listen_pusher_pipeline)
- [ ] **Step 2 [A]:** Chạy thử N=3, DURATION=300 → PASS nếu 0 disconnect ngoài ý muốn
- [ ] **Step 3 [A]:** Cập nhật `soak-test.sh` gọi script này; commit
      `test(selfhost): real-auth multi-user soak harness`
- [ ] **Step 4 [U]:** Chạy soak 30 phút trước khi mời user thứ 2

---

## Self-Review

- [x] Spec coverage: punctuation (T1 — giá trị UX lớn nhất), docs drift (T2),
      multi-user chứng minh (T3). Không có claim nào chưa verify file:line
      (persist call site + api dart + step dart được chỉ lệnh đọc tại chỗ vì
      nội dung có thể đổi giữa các bản merge upstream)
- [x] Placeholder scan: các code block đều hoàn chỉnh; duy nhất Task 3 Step 1
      pseudo-code có ghi rõ file tham chiếu wire format để hoàn thiện
- [x] Type consistency: `punctuate_segments(uid, segments) -> List[TranscriptSegment]`
      khớp call site; env names khớp pattern `OMI_*` hiện có

## Execution Handoff

Chạy Inline trong worktree riêng. Ưu tiên: Task 2 (15 phút) → Task 1 (2-3h) →
Task 3 (2h). Task 1 Step 6 + Task 3 Step 4 cần phối hợp agent chính.
