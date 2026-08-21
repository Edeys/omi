# Omi Self-Hosted Backend — Design Spec

> Date: 2026-08-21
> Status: Approved in chat (brainstorming) — user approved Approach A (Core on VPS, no GPU), n8n RAM limit, keep tele-banking + 9Router, Firebase with step-by-step guidance, fresh data (no migration), desktop-only scope.

## Goal

Run the Omi Windows desktop app (fork at `Edeys/omi`) against a backend **entirely owned by the user**, on their existing VPS (2 vCPU AMD EPYC Gen 3, 4GB RAM, 40GB NVMe, Ubuntu 24.04, IP 103.116.39.65), at **$0/month** — using the existing 9Router LLM gateway, a free CPU speech-to-text engine good for Vietnamese, and a new Firebase project on the free tier.

## Non-Goals (explicitly out of scope for this plan)

- GPU sub-services (diarizer, parakeet, vad, nllb) — no GPU on the VPS; the backend is designed to degrade without them. Adding them later is a config change (provider env vars), not a rewrite.
- Mobile app (Flutter) pointing at the new backend — future work.
- Migrating existing memories/conversations from Omi's cloud — fresh start; old data stays on Omi's cloud for reference.
- Notifications job, memory-maintenance cron, sync-backfill, Stripe billing, integrations (Notion/Whoop/Twitter/…) — not needed for the core "listen + execute commands" purpose. The app must tolerate the missing endpoints (see Degradation).

## Existing infrastructure (verified)

- VPS `103.116.39.65` (DNCloud AMD 1, Ubuntu 24.04): runs `9router` (systemd, LLM gateway `https://9router.xuanloi.me/v1`, OpenAI-compatible, API key in the infra doc), `n8n` (Docker, port 5678), `tele-banking` (systemd). Nginx + certbot installed; UFW only 22/80/443.
- Cloudflare DNS for `xuanloi.me` subdomains.
- Windows app (fork) currently connects to: `https://api.omi.me` (Python backend — data/sync), `https://desktop-backend-hhibjajaja-uc.a.run.app` (desktop backend — chat completions/Gemini proxy), Firebase project `based-hardware` (auth).
- App env vars (`.env.example`): `VITE_FIREBASE_API_KEY/AUTH_DOMAIN/PROJECT_ID`, `VITE_OMI_API_BASE`, `VITE_OMI_DESKTOP_API_BASE`, `VITE_OMI_API_KEY` (dev API key for cloud sync), `VITE_POSTHOG_KEY`, `MAIN_VITE_GOOGLE_CLIENT_ID/SECRET`, `VITE_ENABLE_GOOGLE_INTEGRATION`.

## Architecture

```
Windows desktop app (fork Edeys/omi, branch feat/i18n-vietnamese)
  │
  ├── Firebase Auth  ── project "omi-xuanloi" (new, free tier)
  │     sign-in: app → backend /v1/auth/authorize (Google OAuth, own client)
  │              → backend mints Firebase custom token → app signs in
  │              → backend verifies Firebase ID tokens on every call
  │
  ├── Python backend   omi-api.xuanloi.me  (VPS :8080, Docker)
  │     backend/main.py — conversations, memories, sync, chat sessions
  │
  ├── Desktop backend  omi-desk.xuanloi.me (VPS :8090, Docker)
  │     backend/desktop_backend.py — desktop chat completions, Gemini proxy
  │
  ├── Pusher           omi-ws.xuanloi.me  (VPS :8091, Docker)
  │     streaming audio WebSocket → STT
  │
  ├── STT adapter      (VPS, Docker, port 8092)
  │     sherpa-onnx zipformer-vi-30M-int8 (streaming, CPU, Apache-2.0)
  │     exposes a Deepgram-compatible streaming WebSocket/HTTP endpoint
  │     (backend's DEEPGRAM_SELF_HOSTED_* config path)
  │
  ├── Redis            (VPS, Docker, 127.0.0.1:6379)
  │
  └── LLM → https://9router.xuanloi.me/v1 (existing; OpenAI-compatible)
```

Total new RAM footprint ~1.4–2.0GB on top of the ~1.5–2.0GB already in use → fits 4GB only with the memory limits below.

## Deployment layout on the VPS

- Docker Compose at `/opt/omi/`: services `redis`, `backend`, `desktop-backend`, `pusher`, `stt-adapter`.
- **Mandatory container memory limits** (user-approved): n8n existing compose gets `mem_limit: 1g` (biggest current variable; also `memswap_limit: 1g`); new services: backend ≤1024m, pusher ≤800m, desktop-backend ≤700m, redis ≤200m, stt-adapter ≤500m.
- Swap: add a 2GB swapfile (40GB NVMe has room) as the headroom buffer.
- Nginx vhosts: `omi-api.xuanloi.me` → 127.0.0.1:8080, `omi-desk.xuanloi.me` → 127.0.0.1:8090, `omi-ws.xuanloi.me` → 127.0.0.1:8091 (WS upgrade headers), `omi-stt.xuanloi.me` → 127.0.0.1:8092 (internal only — not exposed publicly; backend reaches it over the Docker network instead; if STT stays internal, no vhost needed).
- Cloudflare: DNS-only A records for the new subdomains → 103.116.39.65 (pattern matches 9router/n8n). SSL via certbot (existing setup).
- UFW stays 22/80/443; all service ports bind to 127.0.0.1 or Docker internal networks only.
- tele-banking and 9router systemd units untouched.

## Firebase & Google setup (step-by-step for the user — Task 2)

1. https://console.firebase.google.com → Add project → name `omi-xuanloi` (any region).
2. **Authentication → Sign-in method → Google: Enable** (Firebase Auth Google provider).
3. **Firestore Database → Create database** → production mode → region (e.g. `asia-southeast1`).
4. **Project settings → Service accounts → Generate new private key** → download JSON (never commit; goes to `/opt/omi/secrets/` on the VPS).
5. **Project settings → General → Your apps → Web app** → copy the web config (`apiKey`, `authDomain`, `projectId`) into the app's `.env`.
6. **Google Cloud Console → APIs & Services → Credentials → Create OAuth client ID → Desktop app** (this is the backend's Google OAuth client — same flow the backend's `routers/auth.py` expects; configure the redirect URI to the backend's `/v1/auth/callback` once the domain is live).
7. Firestore rules: lock to owner-only reads/writes (`request.auth.uid == resource.data.uid` pattern; default deny).

## Backend configuration (Task 4; exact env names verified during Task 1 audit)

- `OPENAI_API_KEY` = 9Router key; OpenAI client base URL = `https://9router.xuanloi.me/v1` (verify the exact env var the backend reads — e.g. `OPENAI_API_BASE`/`OPENAI_BASE_URL` — in Task 1; if the backend only supports fixed OpenAI endpoints, wire 9Router through the OpenRouter-compatible client path instead; decision recorded in Task 1).
- STT: `DEEPGRAM_SELF_HOSTED_ENABLED=1` + self-hosted endpoint = stt-adapter (see `utils/stt/streaming.py`; the repo explicitly supports self-hosted Deepgram-compatible endpoints).
- `ENCRYPTION_SECRET` — generate ≥32 random bytes; `ADMIN_KEY` — random; `CORS_ALLOWED_ORIGINS` — app origin.
- `GOOGLE_CLIENT_ID/SECRET` — from step 6; `FIREBASE_*` — service account + web config.
- `MEMORY_ENABLED=on` (memory extraction is the product core).
- Stripe keys left blank → dev mode skips price validation; Plan/Usage endpoints degrade (app shows its usage-limit UI without billing — acceptable).
- PostHog, ElevenLabs, Perplexity, Twilio, Hume, Pinecone/Typesense, LangSmith — all blank/off. Semantic search degrades (app still works; search falls back).
- `HOSTED_PUSHER_API_URL` → own pusher URL. Diarizer/VAD/NLLB URLs → unset (services degrade to single-stream transcripts, no translation).
- `BASE_API_URL`/`API_BASE_URL` → `https://omi-api.xuanloi.me`.

## STT adapter (Task 6) — sherpa-onnx, Deepgram-compatible

- Python service (FastAPI) wrapping `sherpa-onnx` **online** recognizer with model `sherpa-onnx-zipformer-vi-30M-int8-2026-02-09` (Vietnamese, streaming, int8, ~100MB disk, RTF ≈0.1 on this CPU).
- Implements the Deepgram streaming protocol subset the backend's self-hosted path uses (JSON start/results/close over WebSocket, 16 kHz mono PCM in) — protocol details pinned during Task 1 (read `backend/utils/stt/streaming.py` + `config/stt_provider_policy.py` first).
- Includes its own VAD (sherpa-onnx VAD / endpointing rules) since the backend VAD service is not deployed.
- Lives inside the Docker network; backend calls it by service name.

## App wiring (Task 7)

- `.env` (dev) / build env (installer):
  - `VITE_FIREBASE_API_KEY/AUTH_DOMAIN/PROJECT_ID` → new project's web config
  - `VITE_OMI_API_BASE` → `https://omi-api.xuanloi.me`
  - `VITE_OMI_DESKTOP_API_BASE` → `https://omi-desk.xuanloi.me`
  - `VITE_OMI_API_KEY` → generated via new backend's developer-API-key flow (Settings → Developer) once sign-in works
  - `VITE_POSTHOG_KEY` → blank (analytics off; verify the app treats blank as disabled in Task 1)
- Rebuild (`pnpm run dev` for verification; installer build later).
- Sign-in via Google against the new project; account is fresh (no data migration).

## Security

- Firestore: owner-only rules (step 7 above).
- All secrets live in `/opt/omi/.env` + `/opt/omi/secrets/` (mode 600), never in git.
- SSL via existing certbot/Cloudflare pattern; backend bound to 127.0.0.1 behind nginx.
- `ADMIN_KEY` kept for diagnostics, `ADMIN_KEY_AUTH_ENABLED` stays on only while debugging.
- No ports exposed beyond 80/443.

## Degradation (expected without GPU/paid services — all acceptable)

- No diarizer → transcripts without speaker attribution (single-stream).
- No NLLB → translation UI off.
- No Typesense/Pinecone → semantic search falls back to basic search.
- No Stripe → Plan/Usage tab shows degraded state.
- STT failure → recording retries/fails with a clear error; pusher stays up.
- The app's update checker points at the new backend; a 404 must be treated as "no update" (verify in Task 1 audit; if the app hard-errors, the updater env/feature must be pinned off).

## Verification / acceptance (Task 8)

1. `curl` health endpoints + a sample authed call with `ADMIN_KEY<uid>` (backend's documented dev-auth bypass).
2. Full E2E on the real app: sign in (new Firebase) → record screen+mic session → transcript appears (Vietnamese STT) → conversation saved to Firestore → chat question answered via 9Router → memory extracted.
3. Restart VPS services → data persists, app reconnects, no crash loops (`docker compose ps`, logs clean).
4. RAM check: `free -m` stays under ~3.5GB with swap untouched most of the time.

## Cost

$0/month: VPS already paid, Firebase free tier (Firestore 1GB/50k reads/day), sherpa-onnx free (Apache-2.0), 9Router/LLM on existing infrastructure.

## Task decomposition (for the implementation plan)

1. **App dependency audit** — enumerate every endpoint the Windows app calls on `VITE_OMI_API_BASE` and `VITE_OMI_DESKTOP_API_BASE` (grep `src/renderer/src/lib/apiClient.ts`, `useChat.ts`, `chatSessionsClient.ts`, `sync/convSync`, `main/ipc/auth.ts`, `updater.ts`, `byok.ts`, `mcpExports.ts`), pin the backend env var names (OpenAI base URL, Deepgram self-hosted protocol), and record the degraded-behavior decisions above.
2. **Firebase + Google console setup** — step-by-step walkthrough for the user (steps 1–7 above); output: web config, service account, Google OAuth client, Firestore rules file.
3. **VPS prep** — swap 2GB; Docker compose baseline; n8n `mem_limit: 1g`; nginx vhosts + certbot + Cloudflare DNS; UFW check; measure current RAM/CPU (`free -m`, `docker stats`, `uptime`).
4. **Backend deploy** — build `backend` image (Dockerfile), `.env` per config section, run; verify health + authed curl; desktop-backend image + env (Gemini/Anthropic key via 9Router or direct — per Task 1 decision).
5. **Pusher + Redis** — compose services; verify WS handshake through nginx.
6. **STT adapter** — sherpa-onnx service + Deepgram-compatible surface; verify against a recorded Vietnamese WAV; wire backend `DEEPGRAM_SELF_HOSTED_*`.
7. **App wiring** — new `.env`; dev run; Google sign-in against new project; developer API key; PostHog/updater checks.
8. **E2E verification** — acceptance list above.
9. **Docs** — update `D:\Websites\HUONG-DAN-HA-TANG.md` (new services, ports, subdomains, restart commands) and `desktop/windows/README.md` (self-hosted env section).
