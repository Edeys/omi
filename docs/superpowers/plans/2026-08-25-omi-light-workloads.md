# Omi Self-Host — Light Workloads Plan (cho agent phụ)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.
> Steps dùng checkbox (`- [ ]`). Nhãn [A] = agent làm, [U] = user làm.

**Goal:** Hoàn thành 3 nhóm việc nhẹ còn lại của Omi self-host: (1) benchmark STT
tiếng Việt và cấu hình routing, (2) ép output tiếng Việt, (3) sửa lỗi onboarding
knowledge graph — trong khi agent chính làm các phần khó (scale multi-user,
hybrid STT, speech profile pipeline).

**Architecture:** Không đổi kiến trúc. Task 1 là benchmark + cấu hình env routing
(provider seam có sẵn). Task 2 là env override 1 dòng ở process_conversation.
Task 3 là tolerance 409 phía app Flutter (không đụng backend design).

**Tech Stack:** Python 3.11, Flutter/Dart, Deepgram API, AssemblyAI API, sherpa-onnx.

**Spec:** GitHub Issues Edeys/omi #9, #10, #6 + report
`docs/superpowers/reports/2026-08-25-stt-cloud-keys-setup.md` + AGENTS.md.

## Global Constraints

- Làm việc trong **worktree** từ nhánh `feat/selfhost-backend`; commit lên nhánh đó
- **KHÔNG deploy VPS khi agent chính đang deploy** — ping/đồng bộ trước mỗi lần
  `docker compose build/up` (agent chính đang chạy việc trên cùng VPS)
- Python 3.11; `black --line-length 120 --skip-string-normalization`; TDD fail-first
- Dart: `dart format` line 120; không sửa file `*.g.dart` tay
- Secrets không commit (keys đã nằm trong `/opt/omi/.env` trên VPS)
- Mỗi task 1 commit kèm evidence lệnh đã chạy

---

### Task 1: Benchmark STT tiếng Việt (GitHub Issue #9)

**Files:**
- Create: `selfhost/scripts/stt_benchmark.py`
- Create: `docs/superpowers/reports/2026-08-25-stt-benchmark-results.md`

**Interfaces:**
- Consumes: env `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY` (đã có trong
  `/opt/omi/.env`, container backend đọc được); stt-adapter WS
  `ws://stt-adapter:8092/v1/listen` (trong docker network)
- Produces: bảng so sánh WER/latency/giá + routing decision ghi trong report

- [ ] **Step 1 [A]:** Tạo 3 mẫu audio tiếng Việt (~20-30s mỗi mẫu): 2 mẫu TTS
      (dùng gTTS `lang='vi'`, text tự viết có dấu đầy đủ) + 1 mẫu thu giọng thật
      (nhờ user đọc 1 đoạn 20s, lưu mp3/wav). Lưu text tham chiếu từng mẫu.
- [ ] **Step 2 [A]:** Viết `selfhost/scripts/stt_benchmark.py` chạy từng mẫu qua:
      - **Deepgram Nova-3 batch**: `POST https://api.deepgram.com/v1/listen?model=nova-3&language=multi&punctuate=true`, header `Authorization: Token $DEEPGRAM_API_KEY`, body = bytes audio, Content-Type theo định dạng
      - **AssemblyAI Universal**: `POST /v2/upload` (bytes, header `authorization: $ASSEMBLYAI_API_KEY`) → `POST /v2/transcript` `{"audio_url":..., "speech_model":"universal"}` → poll `GET /v2/transcript/{id}` đến completed
      - **Local adapter**: chạy offline recognizer trực tiếp trong container
        `stt-adapter` trên file wav 16k mono (import `recognizer`,
        `load_offline_engine()` + `ViOfflineRecognizer.transcribe_chunk`)
      - Mỗi engine ghi lại: transcript, thời gian xử lý (không tính upload/poll wait)
- [ ] **Step 3 [A]:** Tính WER bằng `pip install jiwer`:
      `jiwer.wer(reference, hypothesis)` (normalize về thường, bỏ dấu câu trước khi so)
- [ ] **Step 4 [A]:** Viết report `2026-08-25-stt-benchmark-results.md` với bảng
      WER/latency/giá (giá: Deepgram $0.43/h batch, AssemblyAI $0.15/h, local $0)
      + **decision** engine nào làm primary cho tiếng Việt
- [ ] **Step 5 [A]:** Commit `docs(stt): vietnamese benchmark results + routing decision`
- [ ] **Step 6 [A]:** Cấu hình routing theo decision: đọc
      `backend/config/stt_provider_policy.py` + `STT_SERVICE_MODELS` env contract
      (backend/AGENTS.md) → set env trên `/opt/omi/.env` → restart backend
      ⚠️ **[Đồng bộ với agent chính]** trước khi restart
- [ ] **Step 7 [U]:** User test 1 phiên listen thật → xác nhận chất lượng

### Task 2: Ép output tiếng Việt (GitHub Issue #10, phần 1)

**Files:**
- Modify: `backend/utils/conversations/process_conversation.py:291`
- Test: `backend/tests/unit/test_selfhost_output_language.py`

**Interfaces:**
- Consumes: env `OMI_FORCE_OUTPUT_LANGUAGE` (mới); `users_db.get_user_language_preference(uid)`
- Produces: helper `_effective_output_language(uid, language_code) -> str`

- [ ] **Step 1 [A]:** Viết test FAIL:
```python
"""Self-host: OMI_FORCE_OUTPUT_LANGUAGE ép ngôn ngữ output (title/tóm tắt)
khi app gửi language=en nhưng user nói tiếng Việt."""
from unittest.mock import patch


def test_force_env_overrides_everything(monkeypatch):
    monkeypatch.setenv('OMI_FORCE_OUTPUT_LANGUAGE', 'vi')
    with patch('utils.conversations.process_conversation.users_db') as udb:
        udb.get_user_language_preference.return_value = 'en'
        from utils.conversations.process_conversation import _effective_output_language
        assert _effective_output_language('uid', 'en') == 'vi'


def test_no_env_keeps_user_preference(monkeypatch):
    monkeypatch.delenv('OMI_FORCE_OUTPUT_LANGUAGE', raising=False)
    with patch('utils.conversations.process_conversation.users_db') as udb:
        udb.get_user_language_preference.return_value = 'en'
        from utils.conversations.process_conversation import _effective_output_language
        assert _effective_output_language('uid', 'en') == 'en'


def test_no_env_no_preference_falls_back_to_language_code(monkeypatch):
    monkeypatch.delenv('OMI_FORCE_OUTPUT_LANGUAGE', raising=False)
    with patch('utils.conversations.process_conversation.users_db') as udb:
        udb.get_user_language_preference.return_value = None
        from utils.conversations.process_conversation import _effective_output_language
        assert _effective_output_language('uid', 'vi') == 'vi'
```
      Run: `pytest backend/tests/unit/test_selfhost_output_language.py -v` → FAIL
- [ ] **Step 2 [A]:** Implement — tại `process_conversation.py` thêm helper
      (trước hàm chứa dòng 291) và thay dòng 291:
```python
def _effective_output_language(uid: str, language_code: str) -> str:
    """Self-host: OMI_FORCE_OUTPUT_LANGUAGE ép ngôn ngữ output khi app gửi
    language=en nhưng nội dung là tiếng Việt."""
    forced = os.getenv('OMI_FORCE_OUTPUT_LANGUAGE', '').strip()
    if forced:
        return forced
    return users_db.get_user_language_preference(uid) or language_code
```
      dòng 291: `user_language = _effective_output_language(uid, language_code)`
      (kiểm tra `os` đã import ở đầu file)
- [ ] **Step 3 [A]:** Test → PASS cả 3; chạy thêm
      `pytest backend/tests/unit/test_lazy_conversation_processing.py -q` không hồi quy
- [ ] **Step 4 [A]:** `.env.template` + `/opt/omi/.env` thêm
      `OMI_FORCE_OUTPUT_LANGUAGE=vi` (đồng bộ agent chính khi restart);
      black format; commit `feat(selfhost): OMI_FORCE_OUTPUT_LANGUAGE for vietnamese output`
- [ ] **Step 5 [U]:** Ghi 1 hội thoại mới → title/tóm tắt bằng tiếng Việt

### Task 3: Onboarding knowledge graph — tolerate 409 (GitHub Issue #10, phần 2)

**Bối cảnh (đã verify):** onboarding gọi
`KnowledgeGraphApi.rebuildKnowledgeGraph()` (`app/lib/backend/http/api/knowledge_graph_api.dart:27`)
→ backend trả **409** khi canonical state đã tồn tại
(`backend/routers/knowledge_graph.py:78-89`, detail = "Canonical knowledge graph
state is derived from canonical memories...") → màn hình onboarding hiện lỗi đỏ.

**Files:**
- Modify: `app/lib/pages/onboarding/knowledge_graph_step.dart` (đọc file trước khi sửa)
- Modify: `app/lib/backend/http/api/knowledge_graph_api.dart:27`

- [ ] **Step 1 [A]:** Đọc `knowledge_graph_step.dart` để tìm chỗ hiển thị error +
      nút "Thử lại"/"Tiếp tục"
- [ ] **Step 2 [A]:** Sửa `rebuildKnowledgeGraph()`: bắt lỗi 409 → trả về
      `{'skipped': true, 'nodes': []}` thay vì throw:
```dart
try {
  final response = await _client.post('/v1/knowledge-graph/rebuild');
  return response.data;
} on DioException catch (e) {
  if (e.response?.statusCode == 409) {
    // Canonical graph already derived server-side: nothing to rebuild.
    return {'skipped': true, 'nodes': const []};
  }
  rethrow;
}
```
      (điều chỉnh theo HTTP client thật đang dùng trong file)
- [ ] **Step 3 [A]:** Sửa step page: khi `skipped` → coi như hoàn thành
      (auto-advance hoặc hiện "Đồ thị tri thức đã sẵn sàng") thay vì error UI
- [ ] **Step 4 [A]:** `dart format` các file touched; `flutter analyze` không phát
      sinh lỗi mới (so `analysis_baseline.json`)
- [ ] **Step 5 [A]:** Commit `fix(app): tolerate 409 on KG rebuild during onboarding`
- [ ] **Step 6 [A]:** Build APK mới (lệnh như trước, thêm
      `--dart-define=OMI_APP_PROFILE=selfhost`) + upload
      `/var/www/downloads/` trên VPS (đồng bộ agent chính)
- [ ] **Step 7 [U]:** Cài lại APK → onboarding không còn màn hình đỏ

### Task 4 (tuỳ chọn — làm SAU Task 1): Batch STT / voice messages (#6)

**Điều kiện:** Task 1 chốt winner. Nếu winner là Deepgram → voice messages bật được
bằng cách route prerecorded qua Deepgram batch (`backend/utils/stt/pre_recorded.py`
đã có `deepgram_prerecorded_from_bytes`, chỉ cần `DEEPGRAM_API_KEY` — đã có trong env).
Nếu winner không phải Deepgram → lên plan riêng hỏi agent chính trước.

- [ ] **Step 1 [A]:** Đọc `backend/utils/stt/pre_recorded.py` + AGENTS.md Known
      Limitation → đề xuất patch tối thiểu (env `OMI_PRERECORDED_PROVIDER`)
- [ ] **Step 2 [A]:** **Lên plan riêng gửi agent chính duyệt** trước khi code
      (đây là việc chạm upstream design — không tự sửa)

---

## Self-Review

- [x] Spec coverage: #9 (Task 1), #10 cả 2 phần (Task 2 + 3), #6 điều kiện (Task 4)
- [x] Placeholder scan: mọi step có lệnh/code cụ thể; duy nhất Task 3 Step 1-3
      có bước "đọc file trước" vì Dart client chưa được đọc sâu (đã verify path +
      endpoint backend thật)
- [x] Type consistency: helper `_effective_output_language(uid, language_code)`
      khớp call site dòng 291; `skipped` map khớp kiểu trả về `Map<String, dynamic>`
      của `rebuildKnowledgeGraph()`

## Execution Handoff

Chạy Inline trong worktree riêng. **Phối hợp với agent chính**: mọi restart VPS
phải ping trước; deploy APK cuối cùng do agent chính build (chung toolchain).
