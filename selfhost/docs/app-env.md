# App env wiring — Windows desktop against the self-host stack

> **What is this?** The exact `.env` changes that point the Windows desktop app at **our**
> Firebase project (`omi-xuan`) and our VPS backends (`omi-api.xuanloi.me`, `omi-desk.xuanloi.me`)
> instead of Omi's production ones — plus how to run, sign in, and enable cloud sync.
> Time: ~5 minutes for the env + first dev run; ~2 minutes later for the API key.
>
> **Branch:** `feat/selfhost-backend` · **Env file:** `desktop/windows/.env` (git-ignored — local only)

---

## ⚠️ Security — read first

- `desktop/windows/.env` is **git-ignored** (`desktop/windows/.gitignore` → `.env`). It must
  **never** be committed. Real values live only there (and on the VPS in `/opt/omi/.env`).
- The Firebase web `apiKey` is a public client identifier by design, but repo convention
  (see `selfhost/docs/firebase-setup.md`) keeps all real values out of tracked files.
  This guide documents shapes and sources only.
- If you ever paste real values into a committed file or chat: rotate them immediately
  (firebase-setup.md → "If something leaked").

---

## The 7 env changes

Applied to `desktop/windows/.env`. "Before" = Omi production values that shipped with the file;
"After" = self-host values.

| # | Variable | Before (Omi prod) | After (self-host) | Why |
|---|----------|-------------------|-------------------|-----|
| 1 | `VITE_FIREBASE_API_KEY` | `AIzaSyD9dz…kkC8` (based-hardware) | `<omi-xuan web apiKey>` (`AIzaSyBmoo…JLabc`) | Auth must hit **our** Firebase project |
| 2 | `VITE_FIREBASE_AUTH_DOMAIN` | `based-hardware.firebaseapp.com` | `omi-xuan.firebaseapp.com` | Sign-in popup/redirect domain of our project |
| 3 | `VITE_FIREBASE_PROJECT_ID` | `based-hardware` | `omi-xuan` | Firestore + main-process ID-token audience (src/main/auth/firebaseIdToken.ts) |
| 4 | `VITE_OMI_API_BASE` | `https://api.omi.me` | `https://omi-api.xuanloi.me` | Python backend now on the VPS (Task 4) |
| 5 | `VITE_OMI_DESKTOP_API_BASE` | `https://desktop-backend-….run.app` | `https://omi-desk.xuanloi.me` | Desktop backend now on the VPS (Task 4) |
| 6 | `VITE_POSTHOG_KEY` | `phc_z3qU…ez3Y` | *(blank)* | Analytics off. `trackEvent()` early-returns on an empty key (renderer/src/lib/analytics.ts) — nothing leaves the machine |
| 7 | `MAIN_VITE_GOOGLE_CLIENT_ID` | *(blank)* | `<898005165569-…apps.googleusercontent.com>` | The backend OAuth Desktop client created in firebase-setup.md step 6 |

Two more lines are set but **unchanged from before**, listed here so the full file state is unambiguous:

| Variable | Value | Note |
|----------|-------|------|
| `VITE_OMI_API_KEY` | *(blank — for now)* | Filled in after first sign-in, see "Enable cloud sync" below |
| `VITE_ENABLE_GOOGLE_INTEGRATION` | `0` | Google integration stays hidden; no client secret configured yet (`MAIN_VITE_GOOGLE_CLIENT_SECRET` blank) |

Where each value came from:

- #1–3: Firebase console → ⚙ → Project settings → General → Your apps → `omi-desktop` →
  SDK setup and configuration → Config (firebase-setup.md step 5).
- #4–5: DNS/vhost names from `selfhost/docs/cloudflare-dns.md`, served by the Task 4 compose
  stack behind nginx (`selfhost/nginx/omi-api.conf`, `omi-desk.conf`).
- #7: Google Cloud console → APIs & Services → Credentials → OAuth 2.0 Client ID of type
  **Desktop app** (firebase-setup.md step 6).

Consumed by (evidence): renderer/src/lib/firebase.ts (#1–3), src/main/auth/firebaseIdToken.ts (#3),
src/main/ipc/auth.ts + src/renderer/src/lib/apiClient.ts + sync/convSync* (#4),
src/main/assistants/core/session.ts + piMonoSession.ts (#5), analytics.ts (#6),
src/main/integrations/oauth.ts (#7).

---

## Run the app against the new stack

Toolchain: **Node 22 via `C:\Omi\.node22\pnpm.cmd`** — never system Node.

```powershell
cd C:\Omi\desktop\windows
$env:OMI_SANDBOX = 'dev1'          # isolated userData profile for this dev instance
C:\Omi\.node22\pnpm.cmd run dev
```

The app window opens. `OMI_SANDBOX=dev1` pins a separate profile dir + port hash so this
instance doesn't collide with any other dev build (src/main/dev/bench.ts).

### Sign in with Google

1. Click **Sign in with Google** on the app's auth screen.
2. Complete the flow with your Google account. The popup URL will be
   `omi-xuan.firebaseapp.com` — **that is the confirmation you're on the new project**
   (the old one said `based-hardware.firebaseapp.com`).
3. First account on a fresh Firebase project = you are admin; every subsequent user you
   invite signs into the same `omi-xuan` project.

**Verify:** the dev-console sign-in log shows the new auth domain
(`omi-xuan.firebaseapp.com`) and, after sign-in, requests go to `https://omi-api.xuanloi.me`.

### Enable cloud sync (recorded conversations)

The app uploads recorded conversations via `POST /v1/dev/user/conversations/from-segments`,
which requires a developer API key:

1. In the app: **Settings → Developer → Create API key** (this hits the NEW backend).
2. Copy the key into `desktop/windows/.env`:
   ```
   VITE_OMI_API_KEY=<the key you just created>
   ```
3. Stop the dev run, start it again (`pnpm.cmd run dev` — env vars are baked at startup).
4. Record a short conversation, wait for processing, then check the app shows it as synced.
   Backend-side check: the conversation appears in Firestore for your uid under `users/{uid}/…`
   (Firebase console → Firestore Database → Data).

Until step 2 is done, recordings simply save locally only — nothing breaks.

### Typecheck

```powershell
cd C:\Omi\desktop\windows
C:\Omi\.node22\pnpm.cmd run typecheck
```

Runs `tsc --noEmit` over both the node (main) and web (renderer) tsconfigs. Env values are
runtime data — typecheck passes regardless of which project they point at.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Popup says `based-hardware.firebaseapp.com` | Stale dev instance — fully quit Electron, re-run `pnpm.cmd run dev`; electron-vite reloads `.env` only at startup |
| Sign-in error `auth/configuration-not-found` | Google provider not enabled on `omi-xuan` — firebase-setup.md step 2 |
| Sign-in error `auth/unauthorized-domain` | Expected none (electron uses the Firebase SDK, not an authorized-domain redirect); if seen, re-check authDomain value in `.env` |
| API calls fail / timeout | Backend down or DNS wrong — check https://omi-api.xuanloi.me/v1/health returns OK (cloudflare-dns.md, Task 4 verification) |
| ID-token errors in the main process log | `VITE_FIREBASE_PROJECT_ID` mismatch — main process bakes it at startup (src/main/auth/firebaseIdToken.ts), restart required after edits |
| PostHog still sending events | Key not blank in the running instance — check `.env`, restart; empty key disables trackEvent entirely |

---

*Source: plan Global Constraints (docs/superpowers/plans/2026-08-21-omi-selfhost-backend.md) + task-7 brief. Real values live only in the git-ignored `desktop/windows/.env` and `/opt/omi/.env` on the VPS.*
