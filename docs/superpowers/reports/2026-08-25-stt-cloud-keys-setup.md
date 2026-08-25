# Báo cáo: Setup STT Cloud Keys (Deepgram + AssemblyAI)

> **Dành cho agent kế nhiệm / agent khác.** Đọc file này trước khi đụng vào pipeline
> transcription. Ngày: 2026-08-25. Nhánh làm việc: `feat/selfhost-backend`.

## 1. Bối cảnh & quyết định

- User chốt hướng **cloud-first cho STT** vì mục tiêu multi-user: accuracy cao hơn,
  scale theo user, không cần vận hành GPU. Local sherpa-onnx giữ lại làm **fallback**
  (kiến trúc hybrid — đúng cơ chế provider sẵn có của Omi backend).
- Ưu tiên tối đa **chất lượng + tốc độ transcribe tiếng Việt** — đây là tính năng
  top-tier của user (dùng nhiều nhất).
- Giá tham khảo (verified 2026-08): AssemblyAI Universal-2 $0.15/h · Deepgram Nova-3
  $0.43/h batch / $0.46/h streaming · Deepgram tặng $200 credit.

## 2. Đã làm xong

| Hạng mục | Trạng thái |
|---|---|
| Verify Deepgram API key | ✅ auth OK (`GET /v1/projects` → project của user) |
| Verify AssemblyAI API key | ✅ upload endpoint OK |
| Thêm key vào `/opt/omi/.env` trên VPS 103.116.39.65 | ✅ mode 600, backup tại `.env.bak-sttkeys` |
| Recreate container `backend` để nhận env mới | ✅ Up healthy, API health 200 |
| Confirm key trong container | ✅ DG len=40, AA len=32 |

**KHÔNG commit key vào git** — key chỉ nằm ở `/opt/omi/.env` (git-ignored).

## 3. Key nằm ở đâu, ai dùng

- File: `/opt/omi/.env` trên VPS (biến `DEEPGRAM_API_KEY`, `ASSEMBLYAI_API_KEY`)
- Container đọc: `compose-backend-1` (đã restart). Các container khác (desktop-backend,
  stt-adapter) dùng chung `env_file: /opt/omi/.env` nhưng **chưa restart** sau khi thêm
  key — nếu cần dùng key ở container nào thì `docker compose up -d <service>`.
- Local Windows: CHƯA có key trong môi trường dev — nếu cần test local, xin user.

## 4. Việc tiếp theo (chưa ai làm)

1. **Benchmark tiếng Việt**: cùng 1 audio mẫu chạy qua Deepgram Nova-3 /
   AssemblyAI Universal-2 / sherpa-onnx local (streaming zipformer multilingual +
   offline zipformer-vi VietASR) → so WER thực tế + latency + giá.
   ⚠️ Chọn winner rồi mới cấu hình primary/fallback.
2. **Cấu hình routing STT**: cloud = primary, sherpa-onnx local = fallback
   (stt-adapter vẫn chạy, không bỏ). Code backend có sẵn nhánh provider qua env.
3. **Punctuation tiếng Việt**: hiện stt-adapter chỉ pass-through, chưa sinh dấu câu.
4. **Speech profile + diarization**: bị chặn bởi Task 2 docs-parity (GCS buckets +
   billing GCP) — cloud diarization có thể là đường đi nhanh hơn, cân nhắc khi benchmark.
5. **Fix batch/voice-message fail-closed** (Known Limitation trong AGENTS.md).

## 5. File liên quan

- `selfhost/stt-adapter/` — adapter giả lập Deepgram protocol, model sherpa-onnx vi
  (streaming: `zipformer ar_en_id_ja_ru_th_vi_zh-2025-02-10`; offline:
  `zipformer-vi-int8-2025-04-20` VietASR 70k giờ, WER ~10%)
- `docs/superpowers/plans/2026-08-25-omi-selfhost-docs-parity.md` — 5 task còn treo
- `docs/superpowers/plans/2026-08-25-omi-mobile-apk.md` — APK build xong, còn E2E
