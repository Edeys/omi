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

## Bổ sung 26/08: benchmark giọng thật (real voice)

Mẫu: `sample.m4a` (~18.5s) — giọng thật của user, nội dung tự giới thiệu +
giới thiệu dự án Omi. Chạy trên VPS tại `/tmp/bench-real/`.

Lịch sử đo: lần đầu chạy với ref sai 1 từ (*"Đào **Xuyên** Lợi"* thay vì
*"Xuân"* — do người ghi ref đánh máy nhầm); 26/08 chiều đã sửa ref thành
*"Đào Xuân Lợi"* và chạy lại toàn bộ. Bảng dưới là kết quả với **ref đúng**;
WER tái lập giống hệt qua 2 lần chạy độc lập.

### Kết quả giọng thật (ref đúng "Đào Xuân Lợi")

| Engine | WER | Latency | Ghi chú |
|---|---|---|---|
| AssemblyAI universal | **2.44%** 🏆 | ~1.9s | Nghe đúng cả họ tên |
| Deepgram nova-3 `vi` | 4.88% | ~2.3s | Sai "Xuân"→"Xuyên", "Omi"→"Omni" |
| Deepgram nova-2 `vi` | 7.32% | ~2.8s | Thêm "cái", cùng lỗi tên |
| Deepgram nova-3 `multi` | **100%** ❌ | ~1.6s | Thảm họa ngoài tiếng Anh ("project你、你、你、voice]") |
| sherpa local | 12.2% | ~1.0–2.4s | Nhiều lỗi từ ("proc", "recodeng", "vois") |

Đọc kết quả: trên giọng thật, AssemblyAI thắng WER (2.44% vs 4.88%), nhưng
routing **vẫn giữ Deepgram cloud Nova-3 `vi` làm primary** như phần
ROUTING DECISION dưới đây — đây là bề mặt streaming cần kết nối ổn định suốt
phiên, chi phí nằm trong credit $200, và khoảng cách WER đo trên đúng 1 mẫu
18.5s chưa đủ căn cứ đảo provider. Nếu thu thêm mẫu mà AssemblyAI vẫn ổn định
hơn, cân nhắc đưa vào đề xuất cho issue #2 (không sửa trong scope này).

## Verify deploy 26/08 — phiên listen thật qua production

- Runtime container backend: `DEEPGRAM_SELF_HOSTED_ENABLED=false`,
  `OMI_PUNCTUATE_ENABLED=true`; image chứa đủ code Batch-2 (md5 4 file
  `streaming.py` / `punctuation.py` / `process_conversation.py` /
  `stt_provider_policy.py` khớp commit `a4e135975b`) → **không cần rebuild**
  (disk 90%, tránh prune/build khi chưa dọn).
- Phiên test: stream chính `sample.m4a` (18.5s, pcm8 16kHz) qua
  `/v4/listen` production bằng Firebase custom-token auth (uid
  `soak-test-user-0`). Script: `selfhost/scripts/verify_listen_routing.py`.
- Kết quả: server trả `"provider": "deepgram"`; log `Using Deepgram hosted
  API` + `process_audio_dg vi 16000`; transcript hội tụ đầy đủ, có dấu:
  *"Đây là giọng nói của anh, anh là Đào Sơn Lợi Anh đang thực hiện dự án Omi
  Project … đeo vào cổ dùng để recording nghe và thực hiện các lệnh thông qua
  voice"* — không có hiện tượng `project你` của chế độ multi. Streaming nghe
  "Sơn" (batch nghe "Xuyên") — cả hai đều lệch so với "Xuân", nhất quán với
  WER ~4.9% của nova-3 `vi`.

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

- [x] [U] User thu 1 mẫu giọng thật → đã có `sample.m4a` (~18.5s); cột dữ liệu giọng thật ở mục trên
- [x] [A] Set `DEEPGRAM_SELF_HOSTED_ENABLED=false` + container đọc env mới (áp dụng 26/08 ~01:55).
      Verify độc lập 26/08 chiều: runtime flag=`false`, managed client dựng ở hosted endpoint,
      streaming order chuẩn `dg-nova-3,modulate-velma-2,parakeet`; smoke test streaming thực tế
      gộp vào mục dưới (log chưa thấy phiên nào sau khi flip)
- [x] [A] Verify deploy 26/08: image backend chứa đủ code Batch-2 (không cần rebuild dù disk 90%),
      phiên listen thật qua `/v4/listen` → provider=deepgram hosted API, transcript vi có dấu.
      Chi tiết ở mục "Verify deploy 26/08"
- [ ] [U] User test 1 phiên listen thật trên app điện thoại của chính mình (Step 7) — bản verify
      bằng script là đại diện kỹ thuật, chưa thay trải nghiệm end-to-end trên thiết bị
