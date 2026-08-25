# Omi Mobile APK (Self-Host) Build Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development
> (recommended) hoặc superpowers:executing-plans. Steps dùng checkbox (`- [ ]`).

**Goal:** Build APK Omi (dev flavor) trỏ về backend self-host `omi-api.xuanloi.me`,
đăng nhập bằng Google qua Firebase project `omi-xuan`, dùng được: ghi âm → transcribe
→ conversation/memories, chat, notifications — chuẩn bị cho wearable DevKit.

**Architecture:** Dùng nguyên source Flutter upstream (`app/`), KHÔNG fork code —
chỉ cấu hình: (1) `.dev.env` với `API_BASE_URL` self-host; (2) `google-services.json`
của project `omi-xuan` vào flavor dev; (3) toolchain Flutter/JDK/Android SDK cài local.
Docs AppSetup cảnh báo: app và backend **phải cùng Firebase project** (token
project-scoped) — backend mình verify omi-xuan nên app bắt buộc omi-xuan. ✓

**Tech Stack:** Flutter 3.44.5, JDK 21, Android SDK Platform 35, NDK 28.2.13676358
(versions khuyến nghị từ `app/setup.sh`), Windows 10/11 build host.

**Spec:** `app/AGENTS.md` (flavors, generated files, permission matrix) +
docs.omi.me `AppSetup` (manual setup + troubleshooting 401/URL) + `app/lib/env/env.dart`.

## Global Constraints

- Không sửa file generated (`*.g.dart`) tay; regenerate qua build_runner/gen-l10n
- KHÔNG chạy `flutterfire configure` (ghi đè prod credentials — app/AGENTS.md)
- Secrets không commit: `.dev.env`, keystore, google-services.json (kiểm tra .gitignore)
- `dart format` line 120
- Nhãn [A] = agent làm, [U] = user thao tác tay
- Mọi URL backend dùng `https://omi-api.xuanloi.me/` (có dấu `/` cuối — env.dart chuẩn hoá)

---

### Task 1: Cài toolchain build Android trên Windows [A]

**Files:** Create `C:\Omi\toolchain\` (Flutter SDK, Android SDK, JDK — ngoài repo)

**Interfaces:** Produces `flutter`, `java`, `sdkmanager` trên PATH cho các task sau.

- [ ] **Step 1 [A]:** Download Flutter 3.44.5 stable (zip) → giải nén `C:\Omi\toolchain\flutter`;
      thêm `C:\Omi\toolchain\flutter\bin` vào PATH phiên làm việc
- [ ] **Step 2 [A]:** Cài JDK 21 (Temurin zip) → `C:\Omi\toolchain\jdk21`;
      set `JAVA_HOME`
- [ ] **Step 3 [A]:** Android cmdline-tools → `C:\Omi\toolchain\android-sdk\cmdline-tools\latest`;
      `sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0" "ndk;28.2.13676358"`;
      accept licenses: `flutter doctor --android-licenses` (yes hết)
- [ ] **Step 4 [A]:** `flutter doctor -v` — yêu cầu: Flutter OK, Android toolchain OK
      (đĩa C cần ~10GB trống; hiện đủ)
- [ ] **Step 5 [A]:** Ghi lại versions output vào commit message

### Task 2: Firebase Android app cho omi-xuan [U]

- [ ] **Step 1 [U]:** Firebase Console → project `omi-xuan` → Project settings →
      **Add app → Android** → package name **`com.friend.ios.dev`** (đúng flavor dev)
- [ ] **Step 2 [U]:** Tạo keystore debug (agent có thể làm nếu user muốn):
      `keytool -genkey -v -keystore debug.keystore -alias androiddebugkey
      -storepass android -keypass android -dname "CN=Omi Debug" -validity 10000`
      → lấy SHA1/SHA256: `keytool -list -v -keystore debug.keystore -storepass android`
- [ ] **Step 3 [U]:** Thêm SHA1 + SHA256 vào Firebase app vừa tạo (Project settings)
- [ ] **Step 4 [U]:** Download `google-services.json` → đưa agent (đặt vào
      `app/android/app/src/dev/google-services.json`)
- [ ] **Step 5 [A]:** Verify file JSON có `package_name: "com.friend.ios.dev"` +
      `api_key` + `project_id: omi-xuan`; xác nhận file KHÔNG bị git track
      (`git check-ignore` hoặc thêm vào .gitignore nếu chưa)

### Task 3: Cấu hình .dev.env self-host + generate [A]

**Files:** Create `app/.dev.env` (git-ignored)

**Interfaces:** Consumes `lib/env/dev_env.dart` fields (API_BASE_URL, POSTHOG_API_KEY,
GOOGLE_MAPS_API_KEY, INTERCOM_*). Produces `DevEnv.apiBaseUrl` =
`https://omi-api.xuanloi.me/`.

- [ ] **Step 1 [A]:** Viết `.dev.env`:
```
API_BASE_URL=https://omi-api.xuanloi.me/
POSTHOG_API_KEY=
GOOGLE_MAPS_API_KEY=
INTERCOM_APP_ID=
INTERCOM_IOS_API_KEY=
```
      (các field khác nếu dev_env.dart yêu cầu bắt buộc — đọc đủ file trước khi viết)
- [ ] **Step 2 [A]:** `cd app && bash setup.sh android` — chạy pub get + build_runner +
      gen-l10n + flavor config; nếu script đòi tương tác, chạy tay từng bước theo
      Setup Sequence trong app/AGENTS.md
- [ ] **Step 3 [A]:** Grep chống hardcode: `grep -rn "api.omi.me\|omiapi.com" lib/`
      — mọi hit phải đi qua Env.apiBaseUrl; nếu có hardcode → patch tối thiểu + ghi chú
- [ ] **Step 4 [A]:** Commit những thay đổi repo thực sự (nếu chỉ có file ignored
      thì commit docs)

### Task 4: Build APK + cài lên điện thoại [A] + [U]

- [ ] **Step 1 [A]:** `flutter build apk --flavor dev --release`
      Expected: `build/app/outputs/flutter-apk/app-dev-release.apk`
- [ ] **Step 2 [A]:** Copy APK ra nơi user lấy được (`C:\Omi\dist\`)
- [ ] **Step 3 [U]:** Cài APK lên điện thoại Android (sideload, cho phép unknown sources)
- [ ] **Step 4 [U]:** Mở app → đăng nhập Google (chọn tài khoản `xuanloi.me@gmail.com`)
      Expected: vào màn hình chính KHÔNG lỗi 401 (nếu 401 = sai Firebase project —
      xem docs AppSetup troubleshooting)

### Task 5: E2E verify mobile ↔ self-host backend [A] + [U]

- [ ] **Step 1 [U]:** Trên app: ghi âm ngắn (nút mic) → dừng → chờ xử lý
- [ ] **Step 2 [A]:** Verify server-side: conversation mới `source != desktop`,
      status completed, có title/overview; log backend không lỗi
- [ ] **Step 3 [U]:** Chat trên mobile hỏi nội dung vừa ghi → có citation
- [ ] **Step 4 [U]:** Kiểm tra notification (daily summary giờ chạy qua notifications-job)
- [ ] **Step 5 [A]:** Ghi evidence vào commit/PR docs; cập nhật AGENTS.md Known
      Limitations (mobile APK self-host: cách build, các field .dev.env)

---

## Self-Review

- [x] Spec coverage: toolchain (T1), Firebase project-scoped auth (T2 — đúng cảnh
      báo 401 của docs), env injection qua .dev.env/envied đã verify vào
      `lib/env/dev_env.dart` + `env.dart`, build + E2E (T4-T5)
- [x] Placeholder scan: các step có lệnh cụ thể; Step T3-1 ghi chú "đọc đủ file
      trước khi viết" vì field list phải khớp dev_env.dart thật (đã đọc 30 dòng đầu,
      còn vài field nữa cần xem khi làm)
- [x] Type consistency: URL có dấu `/` cuối khớp `env.dart`; package name
      `com.friend.ios.dev` khớp flavor dev trong app/AGENTS.md
- [x] Rủi ro đã ghi: NDK build Opus trên Windows có thể cần Visual Studio
      components — nếu fail sẽ chuyển hướng xử lý tại chỗ (không block các task khác)

## Execution Handoff

Chạy Inline (executing-plans) — 1 agent tự làm được, các bước [U] dừng giao user.
