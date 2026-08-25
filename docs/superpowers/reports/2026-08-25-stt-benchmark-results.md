# STT Benchmark tiếng Việt — Kết quả & Routing Decision (2026-08-26)

> Task 1 của plan `2026-08-25-omi-light-workloads.md`, giải quyết GitHub Issue #9
> (+ liên quan #2). Script: `selfhost/scripts/stt_benchmark.py`; dữ liệu thô:
> `selfhost/scripts/benchmark_results.json`.

## Điều kiện đo

| Mẫu | Nguồn | Độ dài | Nội dung |
|---|---|---|---|
| sample_a | gTTS `lang='vi'` | ~24s | Vườn cà phê, thu hoạch (văn viết chuẩn dấu) |
| sample_b | gTTS `lang='vi'` | ~28s | Sầu riêng Tây Nguyên (có số, giá cả) |

- Chạy trên VPS DNCloud (103.116.39.65), cùng mạng với production containers.
- Engine local chạy offline recognizer **bên trong container `compose-stt-adapter-1`**
  (zipformer-vi-int8, đúng engine production đang dùng).
- Latency = thời gian xử lý thuần (AssemblyAI: trừ poll wait 1s/cuộc; upload không tính).
- WER tính bằng `jiwer`, normalize về chữ thường + bỏ dấu câu.
- ⚠️ Hạn chế: cả 2 mẫu đều là giọng TTS — chưa phản ánh biến điệu giọng người thật.
  Mẫu giọng thật (Step 1c) đang chờ user thu; cập nhật sau nếu cần.

## Kết quả (WER ↓ càng tốt · latency ↓ càng tốt)

### sample_a (cà phê)

| Engine | WER | Latency | Ghi chú |
|---|---|---|---|
| Deepgram nova-3 `multi` | **100%** ❌ | 2.6s | Phiên âm KHÔNG dấu, lẫn Hindi/Trung — không dùng được |
| Deepgram nova-3 `vi` | **1.72%** 🏆 | 1.64s | Đủ dấu, chỉ sai "Mùa"→"Mua" |
| Deepgram nova-2 `vi` | 3.45% | 1.82s | Ổn |
| AssemblyAI universal | 5.17% | 3.36s | Chậm gấp đôi |
| sherpa local | 3.45% | **1.21s** 🏆 | Nhanh nhất, thiếu dấu câu |

### sample_b (sầu riêng)

| Engine | WER | Latency | Ghi chú |
|---|---|---|---|
| Deepgram nova-3 `multi` | **100%** ❌ | 2.5s | Như trên |
| Deepgram nova-3 `vi` | 4.05% | 1.50s | Sai vài từ hiếm |
| Deepgram nova-2 `vi` | **1.35%** 🏆 | 2.00s | Tốt nhất mẫu này |
| AssemblyAI universal | 13.51% ❌ | 3.44s | Suy giảm mạnh với từ chuyên ngành |
| sherpa local | **2.70%** | 1.43s | Rất sát cloud |

### Trung bình 2 mẫu

| Engine | WER TB | Latency TB | Giá | Điểm cộng/trừ |
|---|---|---|---|---|
| 🥇 Deepgram nova-2/nova-3 `vi` | ~2.6% | ~1.7s | $0.43/h (credit $200 còn ~$185) | WER tốt nhất, có punctuation sẵn |
| 🥈 sherpa-onnx local | ~3.1% | ~1.3s | $0 | Nhanh nhất, miễn phí, không có dấu câu |
| 🥉 AssemblyAI universal | ~9.3% | ~3.4s | $0.15/h | WER kém xa 2 bên trên tiếng Việt |

## Phát hiện quan trọng về cấu hình hiện tại

- Backend đang đặt `DEEPGRAM_SELF_HOSTED_ENABLED=true` +
  `DEEPGRAM_SELF_HOSTED_URL=http://stt-adapter:8092` ⇒ toàn bộ token `dg-nova-3`
  trong `STT_SERVICE_MODELS` thực chất đang đi vào **sherpa local**, Deepgram cloud
  key nằm đó **chưa từng nhận traffic** streaming.
- Ngôn ngữ: app gửi `language=vi` → backend resolve `('deepgram', 'vi', 'nova-3')`
  (đúng hướng, vì `vi` nằm trong `deepgram_nova3_languages`, không rơi vào `multi`
  vốn chất lượng thảm họa — phát hiện này nên ghi vào AGENTS.md Known Issues).

## ROUTING DECISION

Theo định hướng **cloud-first đã chốt với user (25/08)** và số liệu trên:

1. **Primary (streaming): Deepgram cloud, model `nova-3`, language `vi`.**
   - WER tốt nhất ở sample_a, punctuation tích hợp, scale theo user không tốn CPU VPS.
   - Áp dụng: `DEEPGRAM_SELF_HOSTED_ENABLED=false` trên `/opt/omi/.env` → token
     `dg-nova-3` tự đi vào `api.deepgram.com`. Không đổi code, đúng seam upstream.
   - Chi phí dự phóng: 2h audio/ngày ≈ $26/tháng — nằm trong credit $200 (~7 tháng).
2. **Fallback/local: giữ `compose-stt-adapter-1` (sherpa) chạy nguyên trạng.**
   - Khi cloud lỗi/không có key, hạ `DEEPGRAM_SELF_HOSTED_ENABLED=true` trở lại là
     quay về local tức thì (chỉ restart backend, không rebuild).
   - ⚠️ Gap ghi nhận: seam upstream **không tự động** fail-over cloud→sherpa trong
     cùng session (chỉ fallback giữa các provider trong preference list). Việc tự
     động hoá cần chạm design upstream → chuyển thành đề xuất cho issue #2,
     KHÔNG sửa trong task này (đúng constraint plan).

## Việc tiếp theo

- [ ] [U] User thu 1 mẫu giọng thật 20s → chạy lại script bổ sung cột dữ liệu giọng thật
- [ ] [A] Ping đồng bộ → set `DEEPGRAM_SELF_HOSTED_ENABLED=false` → restart backend → smoke test
- [ ] [U] User test 1 phiên listen thật (Step 7)
