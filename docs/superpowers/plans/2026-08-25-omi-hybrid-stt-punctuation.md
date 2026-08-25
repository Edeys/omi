# Hybrid STT + Vietnamese Punctuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.
> Steps dùng checkbox (`- [ ]`). Nhãn [A] = agent chính làm, [U] = user làm.
> ⚠️ DEPENDENCY: Task 3 dùng `punctuate_segments()` từ plan
> `2026-08-25-omi-batch2-secondary-agent.md` Task 1 — phải merge trước.

**Goal:** Transcript lưu trữ đạt độ chính xác SOTA tiếng Việt (offline VietASR
70k-giờ re-transcribe thay streaming zipformer) + có dấu câu đầy đủ — live vẫn
hiện tức thì bằng streaming engine.

**Architecture:** Kiểu hybrid 2 tầng đúng tinh thần postprocess của upstream
(trước đây dùng FAL WhisperX đã chết): (1) live giữ nguyên streaming zipformer
cho UX tức thì; (2) lúc post-process, backend gọi endpoint batch MỚI trên
stt-adapter để re-transcribe toàn bộ audio bằng offline VietASR → sanity-check
(theo cơ chế fal_failed có sẵn) → punctuate qua LLM → thay segments trước khi lưu.

**Tech Stack:** Python 3.11, FastAPI WS+HTTP, sherpa-onnx offline VietASR,
pytest, LLM mimo-v2.5 (punctuation, từ Batch 2 Task 1).

**Spec:** report `2026-08-25-stt-cloud-keys-setup.md` + AGENTS.md (postprocess
flow) + `backend/utils/conversations/postprocess_conversation.py` (cơ chế
fal_failed sanity check dòng 126-136).

## Global Constraints

- Worktree từ `feat/selfhost-backend`; push về `Edeys/omi-private`
- Python 3.11; `black --line-length 120 --skip-string-normalization`; TDD fail-first
- Env-gated: `OMI_HYBRID_STT=true` mới bật — tắt = hành vi upstream nguyên vẹn
- Fail-open: mọi lỗi hybrid → fallback về streaming segments (không được mất transcript)
- Offline engine chạy CPU-bound → bắt buộc serialize bằng semaphore (2 vCPU VPS)
- ⚠️ Phối hợp agent chính trước mọi restart VPS; `docker builder prune -f` sau build
- Mỗi task 1 commit kèm evidence; nhãn [A] = agent chính, [U] = user

---

### Task 1: Batch transcribe endpoint trên stt-adapter

**Files:**
- Modify: `selfhost/stt-adapter/main.py` (thêm HTTP endpoint)
- Test: `selfhost/stt-adapter/tests/test_batch_transcribe.py`

**Interfaces:**
- Consumes: `recognizer.load_offline_engine()` + `ViOfflineRecognizer`
  (đã có trong recognizer.py, engine offline VietASR int8)
- Produces: `POST /v1/transcribe-file` — nhận file wav/mp3 (multipart, field
  `file`), query `language=vi`; trả JSON:
  `{"segments": [{"text": str, "start": float, "duration": float}], "duration": float}`
  (text có viết hoa kiểu VietASR — backend tự xử lý)
- Concurrency: semaphore 1 job cùng lúc (offline engine nặng CPU); job vượt
  hàng đợi → 503 ngay (backend sẽ retry)

- [ ] **Step 1 [A]:** Viết test FAIL:
```python
# selfhost/stt-adapter/tests/test_batch_transcribe.py
import io
import wave
from fastapi.testclient import TestClient
import main


def _wav_bytes(seconds=2, freq=440):
    import math, struct
    buf = io.BytesIO()
    w = wave.open(buf, 'w')
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    frames = b''.join(struct.pack('<h', int(3000 * math.sin(2 * math.pi * freq * i / 16000)))
                      for i in range(16000 * seconds))
    w.writeframes(frames); w.close()
    return buf.getvalue()


def test_batch_endpoint_returns_segments(monkeypatch):
    monkeypatch.setattr(main.recognizer_mod, 'load_offline_engine', lambda **kw: object())
    # FakeOfflineRecognizer trả segment cố định — patch create trong endpoint
    client = TestClient(main.app)
    resp = client.post('/v1/transcribe-file?language=vi',
                       files={'file': ('a.wav', _wav_bytes(), 'audio/wav')})
    assert resp.status_code == 200
    data = resp.json()
    assert 'segments' in data and isinstance(data['segments'], list)
    assert 'duration' in data


def test_batch_endpoint_busy_returns_503(monkeypatch):
    # giữ semaphore → request thứ 2 phải 503
    ...
```
      (hoàn thiện fake recognizer theo pattern có sẵn trong
      `tests/test_queryparam_start.py` — ScriptedRecognizer)
      Run: `bash selfhost/stt-adapter/run-tests.sh` → FAIL (endpoint chưa có)
- [ ] **Step 2 [A]:** Implement trong `main.py`:
```python
_BATCH_SEM = asyncio.Semaphore(1)

@app.post('/v1/transcribe-file')
async def transcribe_file(file: UploadFile = File(...), language: str = 'vi'):
    data = await file.read()
    loop = asyncio.get_event_loop()
    def _run():
        engine = recognizer_mod.load_offline_engine(num_threads=int(os.getenv('STT_NUM_THREADS', '2')))
        rec = recognizer_mod.ViOfflineRecognizer(engine_obj=engine)
        # decode wav/mp3 bằng pydub/ffmpeg có sẵn trong image (nếu thiếu -> 400)
        return rec.transcribe_file(data)
    try:
        async with _BATCH_SEM:
            segments = await loop.run_in_executor(None, _run)
    except NotImplementedError:
        raise HTTPException(status_code=400, detail='unsupported audio format')
    return {'segments': segments, 'duration': sum(s.get('duration', 0) for s in segments)}
```
      (điều chỉnh theo API thật của `ViOfflineRecognizer` — đọc
      `recognizer.py` trước; nếu class chưa có `transcribe_file` thì thêm
      method gom toàn bộ chunk rồi decode)
- [ ] **Step 3 [A]:** Test → PASS toàn bộ (cũ + mới); `black` format
- [ ] **Step 4 [A]:** Commit `feat(stt-adapter): batch transcribe endpoint (offline VietASR)`
- [ ] **Step 5 [A]:** Deploy stt-adapter (đồng bộ agent chính); verify:
      `curl -F 'file=@/tmp/test.wav' http://stt-adapter:8092/v1/transcribe-file`
      từ container backend

### Task 2: Backend hybrid post-process (thay FAL bằng adapter batch)

**Files:**
- Modify: `backend/utils/conversations/postprocess_conversation.py:101-136`
- Test: `backend/tests/unit/test_hybrid_postprocess.py`

**Interfaces:**
- Consumes: endpoint Task 1 (httpx qua `utils/http_client.py` seam);
  `punctuate_segments(uid, segments)` từ Batch 2 Task 1;
  env `OMI_HYBRID_STT` (mặc định false)
- Produces: postprocess trả segments = offline VietASR re-transcribe có dấu;
  fail-open về streaming segments khi adapter lỗi (theo cơ chế fal_failed)

- [ ] **Step 1 [A]:** Viết test FAIL: mock httpx POST → adapter trả segments
      hợp lệ → assert `postprocess_conversation` dùng segments mới + punctuation
      được gọi; mock adapter 503 → assert fallback streaming segments nguyên vẹn
      (pattern mock theo `test_postprocess_audio_duration.py` đã có)
- [ ] **Step 2 [A]:** Implement — trong khối try dòng 114-123, THÊM TRƯỚC
      `prerecorded(signed_url, ...)`:
```python
if os.getenv('OMI_HYBRID_STT', '').strip().lower() == 'true':
    from utils.conversations.hybrid_stt import retranscribe_via_adapter
    hybrid = retranscribe_via_adapter(file_path)  # None khi lỗi
    if hybrid:
        fal_segments = hybrid  # dùng luôn, bỏ FAL
```
      + Create `backend/utils/conversations/hybrid_stt.py`:
      `retranscribe_via_adapter(file_path) -> List[TranscriptSegment] | None`
      (httpx POST multipart tới `${STT_ADAPTER_INTERNAL_URL:-http://stt-adapter:8092}/v1/transcribe-file`,
      timeout 120s, parse segments → TranscriptSegment models, map speaker
      giữ nguyên streaming segments theo thứ tự 1:1 nếu số lượng khớp,
      ngược lại gán is_user theo majority)
- [ ] **Step 3 [A]:** Punctuation: sau khi chọn segments cuối cùng (dòng ~144),
      gọi `punctuate_segments(uid, conversation.transcript_segments)`
      (từ Batch 2 Task 1) trước `persist_processed_conversation`
- [ ] **Step 4 [A]:** Test → PASS; chạy toàn bộ
      `pytest backend/tests/unit/ -k "postprocess or hybrid or punctuat" -q`
- [ ] **Step 5 [A]:** `.env.template` + `/opt/omi/.env`: `OMI_HYBRID_STT=true`;
      black; commit `feat(selfhost): hybrid STT - offline VietASR re-transcription via adapter`
- [ ] **Step 6 [A]:** Deploy backend (đồng bộ agent chính)
- [ ] **Step 7 [U]:** Ghi 1 hội thoại mới → conversation lưu xong → mở transcript:
      chữ phải CÓ DẦU CÂU + chính xác hơn bản live. So sánh WER cảm nhận trước/sau.

### Task 3: Force language=vi trên adapter + dọn log

**Files:**
- Modify: `selfhost/stt-adapter/main.py:107` (query-param auto-start)
- Test: `selfhost/stt-adapter/tests/test_force_language.py`

- [ ] **Step 1 [A]:** Test FAIL: query `language=multi` + env
      `STT_FORCE_LANGUAGE=vi` → session phải start với language='vi'
- [ ] **Step 2 [A]:** Implement: trong auto-start payload, nếu
      `os.getenv('STT_FORCE_LANGUAGE')` set → override `payload['language']`
- [ ] **Step 3 [A]:** Test PASS; `.env.template` thêm `STT_FORCE_LANGUAGE=vi`;
      commit `feat(stt-adapter): STT_FORCE_LANGUAGE override (multi -> vi)`
- [ ] **Step 4 [A]:** Deploy stt-adapter

### Task 4: E2E verify + tune

- [ ] **Step 1 [U]:** Ghi 2 hội thoại thật (1 ngắn 30s, 1 dài 5 phút)
- [ ] **Step 2 [A]:** Đo: thời gian finalization, chất lượng transcript
      (dấu câu + độ chính xác), lỗi trong log
- [ ] **Step 3 [A]:** Tuning nếu cần: số threads offline engine
      (`STT_NUM_THREADS`), semaphore count, prompt punctuation
- [ ] **Step 4 [A]:** Cập nhật AGENTS.md Known Limitations → chuyển
      "punctuation pass-through" sang "hybrid STT hybrid pipeline" + commit docs

---

## Self-Review

- [x] Spec coverage: re-transcribe SOTA (T1-T2), punctuation (T2 Step 3, phụ thuộc
      Batch 2 T1), language forcing (T3), E2E (T4)
- [x] Placeholder scan: code skeleton đầy đủ; các chỗ "điều chỉnh theo API thật"
      là điểm BẮT BUỘC đọc file thật (recognizer.py API chưa có method
      transcribe_file — executor phải đọc + hoàn thiện, đã ghi rõ hướng)
- [x] Type consistency: endpoint trả `{segments, duration}` khớp parser
      `retranscribe_via_adapter`; fail-open khớp cơ chế fal_failed có sẵn

## Execution Handoff

Agent chính thực hiện Inline (executing-plans) — các bước [U] dừng cho user.
**Dependency:** Batch 2 Task 1 (punctuate_segments) phải merge trước Task 2.
