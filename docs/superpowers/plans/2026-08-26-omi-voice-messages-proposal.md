# Omi Self-Host — Plan: Voice Messages (batch STT) theo winner benchmark (P1-T4)

> **Trạng thái: DỰ THẢO — chờ agent chính duyệt trước khi code** (đúng constraint
> plan Light Workloads Task 4 Step 2: "việc chạm upstream design — không tự sửa").
>
> Spec: GitHub Issue Edeys/omi #6 + Known Limitation hiện tại trong `AGENTS.md`
> dòng 77 ("Voice messages / batch STT fail closed by design").

## Bối cảnh đã verify

- Winner benchmark T1: **Deepgram nova-3 `vi`** (WER ~2.6%, có punctuation sẵn).
- Seam upstream **đã có sẵn**: `deepgram_prerecorded_from_bytes` trong
  `backend/utils/stt/pre_recorded.py:392`, nhận WAV/PCM16, route qua
  `api.deepgram.com`, `punctuate=True, smart_format=True`.
- Lý do đang fail-closed: `DEEPGRAM_API_KEY` trống → `_get_deepgram_client()`
  raise `CONFIG_ERROR` (`pre_recorded.py:139-148`). Trên VPS key ĐÃ CÓ trong
  `/opt/omi/.env` — tức là **không cần sửa code để bật**, chỉ thiếu đường wire
  từ voice-message endpoint vào seam này.

## Thiết kế đề xuất (tối thiểu, env-gated)

1. **Env mới:** `OMI_PRERECORDED_PROVIDER` (`none` | `deepgram`, mặc định
   `none` = giữ nguyên hành vi fail-closed hiện tại).
2. **Call boundary:** nơi xử lý voice message (endpoint nhận audio file của
   chat/messages) — khi `OMI_PRERECORDED_PROVIDER=deepgram`:
   - đọc bytes audio, gọi `deepgram_prerecorded_from_bytes(..., language='vi')`;
   - ghép words thành text (kèm speaker nếu diarize) rồi đưa vào pipeline chat
     như một tin nhắn text thường.
3. **Fail-open ở tầng UX:** provider lỗi → trả thông báo "không transcribe được
   tin nhắn thoại" cho user, KHÔNG làm crash request; log không in raw transcript
   (`log_sanitizer`).
4. **Không đụng** streaming realtime `/v4/listen`, không đụng
   `config/prerecorded_stt.py` contract (thêm token model thì phải cập nhật
   contract + tests đi kèm — tránh vì chỉ set language='vi' trên nova-3 có sẵn).

## Chi phí dự phóng

Voice messages ~5 phút audio/ngày × $0.43/h ≈ **$1.1/tháng**, nằm trong credit
$200 Deepgram (~7 tháng cùng streaming).

## Rủi ro / lưu ý phối hợp

- Restart backend VPS phải ping agent chính.
- Nếu agent chính đang refactor `pre_recorded.py` cho hybrid STT realtime punct
  (plan hard-tasks) → merge sau, nhánh riêng.

## Steps (khi được duyệt)

- [ ] [A] TDD test `backend/tests/unit/test_selfhost_voice_message.py`: env off
      → không gọi deepgram; env on + mock → text ghép đúng; provider raise →
      fail-open message.
- [ ] [A] Implement call boundary + env gate.
- [ ] [A] black format, commit `feat(selfhost): voice messages via deepgram prerecorded (env-gated)`.
- [ ] [U] Deploy + test gửi 1 voice message thật.
