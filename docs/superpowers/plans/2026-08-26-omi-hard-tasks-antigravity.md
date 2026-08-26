# Omi Self-Host — Hard Tasks (Antigravity Spec)

**For:** Antigravity agent (không có superpowers plugin). Đọc file này + thực hiện theo thứ tự Task 1 → 4.

**Goal:** Hoàn thiện 4 năng lực khó còn thiếu của self-host: (1) Hybrid STT + realtime punctuation tiếng Việt, (2) Soak test đa user với auth thật + capacity matrix, (3) Speech-profile & diarization pipeline (billing-gated), (4) Harness debug mobile qua adb thay vì đoán bằng simulator.

**Context / Quyết định đã chốt:**
- Cloud-first STT, local sherpa-onnx fallback (`docs/superpowers/reports/2026-08-25-stt-cloud-keys-setup.md`)
- Batch punctuation tiếng Việt là tiền đề của realtime (Batch-2 Task 1 tạo `backend/utils/conversations/punctuation.py` với `punctuate_segments`)
- Modal GPU services (VAD/speaker-ID) đã có code `backend/modal/main.py`, deploy qua `selfhost/modal/deploy.sh` khi cần
- VPS: `feat/selfhost-backend`, 2vCPU/4GB, 7 containers healthy; deploy phải ping agent chính trước khi `docker compose build/up`

**Tech Stack:** Python 3.11, FastAPI, websockets, sherpa-onnx, Deepgram SDK 4.8.1, AssemblyAI SDK, Modal (T4), Flutter (đã có toolchain), ADB (platform-tools), Firestore, Redis.

**Spec / Docs cần đọc trước khi code:**
- `docs.omi.me` Real-time Transcription (`/v4/listen`, `interim_results`, VAD gating)
- `backend/AGENTS.md` (Service Map, Async I/O 3-Lane, WebSocket Concurrency)
- `backend/config/stt_provider_policy.py` + `STT_SERVICE_MODELS` env contract
- `docs/superpowers/plans/2026-08-25-omi-selfhost-docs-parity.md` Task 2 (buckets) — hiểu GCS billing gate

**Yêu cầu chung:**
- Python 3.11, format `black --line-length 120 --skip-string-normalization` cho mọi file Python
- Secrets không commit (`/opt/omi/.env` mode 600, `google-services.json`, `*.keystore`)
- Làm việc trong worktree từ `feat/selfhost-backend`, commit lên nhánh đó
- Mỗi Task có test đi kèm, chạy được bằng `pytest`
- Log không in raw transcript (dùng `log_sanitizer` nếu log)

---

## Files sẽ tạo / sửa

**Tạo mới:**
- `backend/utils/stt/punctuation_llm.py`
- `backend/tests/unit/test_hard_punctuation_realtime.py`
- `backend/tests/unit/test_hard_scale_soak.py`
- `selfhost/scripts/soak-real-auth.py`
- `tools/adb_logcat.py` + `tools/check-adb-device.sh`
- `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md`

**Sửa:**
- `selfhost/stt-adapter/main.py:91-148` (thêm hybrid fallback + hook punctuation, sau `encode_results`)
- `AGENTS.md` (fork section, sau khi Task 2-3 xong)

---

### Task 1 — Hybrid STT + Realtime Vietnamese Punctuation

**Mục tiêu:** Khi STT streaming đang chạy, nếu `OMI_PUNCTUATE_REALTIME=true` và ngôn ngữ `vi`, text phải được chèn dấu câu trước khi gửi về client. Fail-open: lỗi LLM thì trả nguyên văn.

**Yêu cầu:**
- Env: `OMI_PUNCTUATE_REALTIME` (default `false`), `OMI_LIGHT_MODEL` (default `mimo-v2.5`), `OMI_PUNCTUATE_ENABLED` (đã có từ Batch-2)
- Interface: `punctuate_text_realtime(text: str, language: str = "vi") -> str`
- Dùng provider có sẵn: `utils.llm.providers.get_or_create_openai_compatible_llm('openai', model)`

**Các bước:**
1. Tạo file `backend/utils/stt/punctuation_llm.py` với prompt: "Bạn là bộ chèn dấu câu cho bản ghi tiếng Việt. Viết lại CHÍNH XÁC văn bản sau, chỉ THÊM dấu câu (.,?!...) và viết hoa chữ cái đầu nếu cần. KHÔNG đổi từ, KHÔNG thêm/xóa/dịch. Chỉ trả về văn bản đã sửa, không giải thích."
   - Hàm `_get_llm()` đọc `OMI_LIGHT_MODEL`
   - Hàm `punctuate_text_realtime` kiểm tra `language` startswith `vi` và env gate, gọi `llm.invoke(_PROMPT + text)`, strip và trả về, catch exception → return input + `logger.warning`.

2. Viết test `backend/tests/unit/test_hard_punctuation_realtime.py` (3 case):
   - Mock LLM trả về `"Xin chào bạn. Tôi là Nam."` → assert text được sửa
   - Mock LLM raise RuntimeError → assert trả nguyên văn (fail-open)
   - Set `OMI_PUNCTUATE_REALTIME=false` → assert không gọi LLM, trả nguyên văn
   - Dùng `unittest.mock.patch("backend.utils.stt.punctuation_llm._get_llm", return_value=llm)`

3. Chạy: `pytest backend/tests/unit/test_hard_punctuation_realtime.py -v` → phải PASS 3/3

4. Wire vào adapter: trong `selfhost/stt-adapter/main.py` vòng `for segment in segments:` trước `encode_results`, thêm:
   ```python
   if os.getenv("OMI_PUNCTUATE_REALTIME", "").lower() == "true" and segment.get("language", "vi").startswith("vi"):
       from punctuation_llm import punctuate_text_realtime
       segment["text"] = punctuate_text_realtime(segment["text"], language=segment.get("language", "vi"))
   ```

**Tiêu chí hoàn thành & Self-Verify:**
- [ ] Test file tồn tại: `backend/tests/unit/test_hard_punctuation_realtime.py`
- [ ] Chạy `pytest backend/tests/unit/test_hard_punctuation_realtime.py -v` đạt **PASS 3/3**
- [ ] Code tuân thủ fail-open (không raise exception ra ngoài khi LLM lỗi hoặc timeout)
- [ ] Chạy `black --line-length 120 --skip-string-normalization backend/utils/stt/punctuation_llm.py selfhost/stt-adapter/main.py backend/tests/unit/test_hard_punctuation_realtime.py`
- [ ] Commit: `git commit -m "feat(stt): hybrid realtime vi punctuation (mimo-v2.5, env-gated, fail-open)"`

---

### Task 2 — Multi-User Scale Hardening (Real-Auth Soak + Capacity Matrix)

**Mục tiêu:** Chứng minh hệ thống chịu được 5 user đồng thời 10 phút với auth thật (không phải health-check giả), xuất báo cáo capacity.

**Yêu cầu:**
- Env đọc từ `/opt/omi/.env`: `GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase-service-account.json`, `FIREBASE_API_KEY`, `HOSTED_PUSHER_API_URL`
- CLI: `python selfhost/scripts/soak-real-auth.py --users 5 --duration 600 --ramp 60` → exit 0 nếu không WS crash và `recovering stale < 5`

**Các bước:**
1. Tạo `selfhost/scripts/soak-real-auth.py`:
   - Dataclass `SoakConfig(users=5, duration=600, ramp_seconds=60, silence_interval=5.0)`
   - `mint_custom_token(uid: str) -> bytes` dùng `firebase_admin.auth.create_custom_token(uid)`
   - `run_one_user(uid, duration, silence_interval)`: exchange custom token → ID token qua `identitytoolkit.googleapis.com`, mở WS `wss://.../v4/listen`, gửi PCM16 silence 600ms mỗi 5s, log disconnect/error
   - `main(cfg)`: tạo N uid `soak-{i}`, staggered ramp, `asyncio.gather` supervise/drain, đếm `docker compose logs backend --since` recovering stale

2. Viết test `backend/tests/unit/test_hard_scale_soak.py`:
   - `test_mint_custom_token_uses_firebase_admin` (patch `firebase_admin.auth.create_custom_token`)
   - `test_soak_config_defaults` (assert ramp=60, interval=5.0)

3. Chạy thử ngắn: `python selfhost/scripts/soak-real-auth.py --users 3 --duration 60 --ramp 10` → 0 crash, in recovering stale count

4. Chạy đủ 600s với 5 user, thu thập `free -h`, `df -h`, `docker stats --no-stream`, điền `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md`:
   ```
   | Users | RAM peak | CPU p50 | Finalization p95 | Stale recoveries | Verdict |
   | 5 | 2.1G/3.7G | 28% | 1.8s | 2 | PASS |
   ```
   Ghi khuyến nghị 8vCPU/32GB cho 10-50 users (theo `backend/charts/*/values.yaml` đã thu thập).

**Tiêu chí hoàn thành & Self-Verify:**
- [ ] Test file tồn tại: `backend/tests/unit/test_hard_scale_soak.py`
- [ ] Chạy `pytest backend/tests/unit/test_hard_scale_soak.py -v` đạt **PASS 100%**
- [ ] Script soak `selfhost/scripts/soak-real-auth.py` chạy dry-run thành công
- [ ] File báo cáo `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md` có đầy đủ bảng số liệu và mục khuyến nghị tài nguyên
- [ ] Chạy `black --line-length 120 --skip-string-normalization selfhost/scripts/soak-real-auth.py backend/tests/unit/test_hard_scale_soak.py`
- [ ] Commit: `git commit -m "feat(selfhost): real-auth multi-user soak harness + capacity matrix"`

---

### Task 3 — Speech-Profile & Speaker Diarization Pipeline (Billing-Gated)

**Mục tiêu:** Khi `BUCKET_SPEECH_PROFILES` chưa cấu hình (chờ billing GCP), hệ thống phải fail-open (diarization tắt, không crash). Khi bucket có, probe phải trả về true.

**Yêu cầu:**
- File: `backend/utils/other/storage.py` gần `_get_speech_profiles_bucket()`
- Interface: `ensure_speech_profile_bucket(uid: str) -> bool`

**Các bước:**
1. Viết test `backend/tests/unit/test_hard_speech_profile.py` (2 case):
   - `BUCKET_SPEECH_PROFILES` unset → `ensure_speech_profile_bucket("uid") is False`
   - Set `my-bucket`, mock `_get_storage_client().bucket().exists() -> True` → assert True

2. Implement trong `storage.py`:
   ```python
   def ensure_speech_profile_bucket(uid: str) -> bool:
       bucket = _get_speech_profiles_bucket()
       if bucket is None:
           return False
       try:
           return bool(bucket.exists())
       except Exception as e:
           logger.warning("speech profile bucket probe failed uid=%s: %s", uid, e)
           return False
   ```

3. Kiểm tra `upload_profile_audio` và `get_profile_audio_if_exists` đã trả `None/False` khi bucket None (storage.py:104-117) — không cần sửa thêm, chỉ cần ghi vào `AGENTS.md` rằng tính năng này billing-gated.

**Tiêu chí hoàn thành & Self-Verify:**
- [ ] Test file tồn tại: `backend/tests/unit/test_hard_speech_profile.py`
- [ ] Chạy `pytest backend/tests/unit/test_hard_speech_profile.py -v` đạt **PASS 2/2**
- [ ] Cập nhật `AGENTS.md` (Known Limitations) và `selfhost/.env.template`
- [ ] Chạy `black --line-length 120 --skip-string-normalization backend/utils/other/storage.py backend/tests/unit/test_hard_speech_profile.py`
- [ ] Commit: `git commit -m "feat(selfhost): speech-profile bucket probe (billing-gated, fail-open)"`

---

### Task 4 — Mobile Deep-Debugging Harness (thay simulator)

**Mục tiêu:** Có tool gõ 1 lệnh là lấy được log thật từ điện thoại thay vì đoán lỗi.

**Yêu cầu:**
- Tool: `tools/adb_logcat.py` CLI `python -m tools.adb_logcat --package com.friend.ios.dev --filter "GoogleSignIn|ApiException" --since 60`
- Device: Pixel 4 đã bật Developer options + USB debugging, adb tại `C:\Omi\toolchain\android-sdk\platform-tools\adb.exe`

**Các bước:**
1. Tạo `tools/adb_logcat.py`:
   - Hằng `ADB = Path(r"C:\Omi\toolchain\android-sdk\platform-tools\adb.exe")`
   - `fetch_logcat(package, filters, since_seconds) -> str`: chạy `adb logcat -d -v time`, lọc theo package/flutter, lọc theo regex filters, giữ 500 dòng cuối
   - CLI argparse như spec.

2. Tạo `tools/check-adb-device.sh` (hoặc `.py`): chạy `adb devices -l` + `Get-PnpDevice` WPD check, hàm `parse_devices_output(sample) -> list[dict]`.

3. Viết test `tests/unit/test_adb_logcat.py`:
   - Mock `subprocess.run` trả về fake logcat có dòng `W/Auth: Server returned error` và `I/flutter: OAuth Google sign in error` → assert filter giữ lại 2 dòng
   - `parse_devices_output("9B061FFAZ00E5C device product:flame...")` → assert dict

4. Verify thủ công: cắm Pixel 4 ở File Transfer mode, chạy `python -m tools.adb_logcat --package com.friend.ios.dev --filter "Auth flutter" --since 60` → phải thấy log thật.

**Tiêu chí hoàn thành & Self-Verify:**
- [ ] Test file tồn tại: `tests/unit/test_adb_logcat.py`
- [ ] Chạy `pytest tests/unit/test_adb_logcat.py -v` đạt **PASS 100%**
- [ ] Tool CLI `tools/adb_logcat.py` và check device script hoạt động đúng
- [ ] Chạy `black --line-length 120 --skip-string-normalization tools/adb_logcat.py tools/check_adb_device.py tests/unit/test_adb_logcat.py`
- [ ] Commit: `git commit -m "feat(tools): adb logcat wrapper (replaces phone-simulator guesses)"`

---

## Cách chạy (Antigravity)

1. **Khởi tạo Worktree riêng biệt:**
   ```powershell
   git worktree add C:\Omi\omi-hard feat/selfhost-backend
   cd C:\Omi\omi-hard
   ```
2. **Thực hiện tuần tự:** Làm lần lượt từng Task theo thứ tự: **Task 1 → Task 2 → Task 3 → Task 4**. Mỗi Task tuân thủ quy trình TDD (Test trước → Test FAIL → Viết code → Test PASS).
3. **Format code trước khi commit:** Bắt buộc chạy `black` trên mọi file Python mới tạo hoặc chỉnh sửa:
   ```powershell
   black --line-length 120 --skip-string-normalization <file_can_format>
   ```
4. **Mỗi Task 1 commit:** Sau khi hoàn thành và tự verify một task, tạo 1 commit với message tương ứng trước khi chuyển sang task kế tiếp.
5. **Quy tắc an toàn VPS:** Không tự ý `docker compose build/up` trên VPS nếu chưa ping / xác nhận trước với agent phụ trách deploy.

---

## Bàn giao & Checklist Nghiệm thu

Khi hoàn tất 4 Task, agent thực hiện kiểm tra chéo và báo cáo:
- [ ] **Task 1:** `pytest backend/tests/unit/test_hard_punctuation_realtime.py -v` (3/3 PASS)
- [ ] **Task 2:** `pytest backend/tests/unit/test_hard_scale_soak.py -v` (PASS 100%) & file report `docs/superpowers/reports/2026-08-26-hard-tasks-scale-matrix.md`
- [ ] **Task 3:** `pytest backend/tests/unit/test_hard_speech_profile.py -v` (2/2 PASS) & `AGENTS.md` cập nhật
- [ ] **Task 4:** `pytest tests/unit/test_adb_logcat.py -v` (PASS 100%) & CLI tool sẵn sàng
- [ ] Tất cả file Python sạch chuẩn `black`
- [ ] 4 commits tương ứng đã được ghi nhận trên branch.
