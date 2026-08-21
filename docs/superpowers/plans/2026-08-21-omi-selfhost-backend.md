# Omi Self-Hosted Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Tasks marked `[USER]` require the human partner to act** (Firebase console clicks, SSH to the VPS, app sign-in) — a subagent cannot do those; it delivers the scripts/instructions and the user runs them, then reports back.

**Goal:** Run the Omi Windows app against a fully self-hosted backend on the user's VPS (2 vCPU/4GB/40GB) at $0/month, using 9Router for LLM, sherpa-onnx (CPU, Vietnamese) for STT, and a new Firebase project.

**Architecture:** Docker Compose on the VPS (`redis`, `backend`, `desktop-backend`, `pusher`, `stt-adapter`), behind nginx + Cloudflare SSL. App `.env` repointed to new Firebase + subdomains. GPU services deliberately not deployed; the backend degrades gracefully (single-stream transcripts, no NLLB translation).

**Tech Stack:** Python FastAPI (repo `backend/`), Docker Compose, nginx/certbot, sherpa-onnx (Apache-2.0, `zipformer-vi-30M-int8-2026-02-09`), Firebase (Auth + Firestore free tier), 9Router OpenAI-compatible gateway.

**Spec:** `docs/superpowers/specs/2026-08-21-omi-selfhost-backend-design.md` (the plan argues from the spec; executors read both).

## Global Constraints

- VPS `103.116.39.65` (Ubuntu 24.04, 2 vCPU EPYC Gen3, 4GB RAM, 40GB NVMe). Total RAM must stay under ~3.5GB: add a 2GB swapfile; every container gets a hard `mem_limit` (n8n ≤1g — existing compose edited; backend ≤1024m, pusher ≤800m, desktop-backend ≤700m, redis ≤200m, stt-adapter ≤500m).
- **Do not break existing services**: 9Router (systemd `9router`, port 20128, API key in `D:\Websites\HUONG-DAN-HA-TANG.md`) and tele-banking (systemd) stay untouched. n8n stays but with the memory limit.
- No GPU sub-services. Stripe/PostHog/ElevenLabs/Perplexity/Twilio/Hume/Pinecone/Typesense all off (blank env).
- New DNS (Cloudflare, DNS-only A records → `103.116.39.65`): `omi-api.xuanloi.me`, `omi-desk.xuanloi.me`, `omi-ws.xuanloi.me`. SSL via certbot. UFW stays 22/80/443.
- Firebase project name `omi-xuanloi`; Firestore rules owner-only.
- All secrets live in `/opt/omi/.env` and `/opt/omi/secrets/` (mode 600); NEVER committed. The repo carries only `.env.template` (placeholders) and `secrets/.gitignore`.
- Local app toolchain: Node 22 via `C:\Omi\.node22\pnpm.cmd` (never system Node 24). App repo is `C:\Omi` (branch `feat/selfhost-backend` for these tasks; the i18n work stays on `feat/i18n-vietnamese`).
- Self-host artifacts live in `C:\Omi\selfhost/` (scripts, compose, nginx conf, docs, stt-adapter). Committed on `feat/selfhost-backend`.
- App env vars to change: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_OMI_API_BASE`, `VITE_OMI_DESKTOP_API_BASE`, `VITE_OMI_API_KEY`, `VITE_POSTHOG_KEY` (blank).
- Commit style: conventional (`chore:`, `feat:`, `fix:`, `docs:`). Format Python with `black --line-length 120 --skip-string-normalization`; JSON with 4-space indent.

---

### Task 1: App dependency audit

**Files:**
- Create: `selfhost/docs/app-dependency-audit.md`
- (read-only over the repo — no source changes)

**Interfaces:**
- Consumes: nothing.
- Produces: `selfhost/docs/app-dependency-audit.md` — the authoritative endpoint table and env decisions every later task cites.

- [ ] **Step 1: Enumerate the Python-backend surface**

Read and list every HTTP/WS call the Windows app makes against `VITE_OMI_API_BASE`. Sources to grep (paths under `C:\Omi\desktop\windows\src`): `renderer/src/lib/apiClient.ts`, `renderer/src/lib/useChat.ts`, `renderer/src/lib/chatSessionsClient.ts`, `renderer/src/lib/chatAttachmentUpload.ts`, `renderer/src/lib/xSession.ts`, `renderer/src/lib/aiProfileHost.ts`, `renderer/src/lib/sync/convSync*`, `main/ipc/auth.ts`, `main/ipc/byok.ts`, `main/ipc/mcpExports.ts`, `main/updater.ts`. Produce a table: `endpoint | method | purpose | needed for core (listen+chat+memory)? | degraded behavior if missing`.

- [ ] **Step 2: Enumerate the desktop-backend surface**

Same for `VITE_OMI_DESKTOP_API_BASE`: grep `renderer/src/lib/geminiClient.ts`, `renderer/src/lib/piMonoAuthHost.ts`, `renderer/src/lib/rewindEmbedHost.ts`, `renderer/src/main/assistants/core/session.ts`, `renderer/src/main/codingAgent/piMonoSession.ts`, `renderer/src/main/automation/planner.e2e.test.ts` (env default). Table of endpoints on the desktop backend.

- [ ] **Step 3: Pin backend env decisions**

In `C:\Omi\backend`, read `utils/llm/clients.py`, `utils/stt/streaming.py`, `config/stt_provider_policy.py`, `database/_client.py`, `utils/env_loader.py`, `routers/auth.py`. Record in the audit doc, each with file:line evidence:
- The exact env var (or absence) controlling the OpenAI client base URL (e.g. `OPENAI_BASE_URL` / `OPENAI_API_BASE` / hardcoded) — and, if hardcoded to `api.openai.com`, the chosen way to reach 9Router: OpenRouter-compatible client path or a local reverse-proxy env override. This is the LLM wiring decision.
- The exact `DEEPGRAM_SELF_HOSTED_*` env var set and the Deepgram streaming protocol surface the backend consumes (message types, binary framing, sample rate) — this pins the STT adapter's wire contract.
- Whether the app's update check tolerates a 404 from `VITE_OMI_API_BASE` (read `main/updater.ts`) — if it hard-errors, record the env/flag to disable updates.
- Whether blank `VITE_POSTHOG_KEY` disables analytics (read `renderer/src/lib/analytics*` / `main/observability`) — if not, record what must change.
- The `ADMIN_KEY<uid>` dev-auth bypass path (read `utils/other/endpoints.py` / auth deps) so Task 4's authed curl works.
- The health routes (verified in `backend/routers/other.py:8` → `/v1/health`; `backend/routers/desktop_core.py:77,82` → `/health`, `/ready`; `backend/pusher/main.py:66` → `/health`).

- [ ] **Step 4: Verify + commit**

Re-read the audit doc for contradictions; every "degradation" claim in the spec must map to a table row. Commit: `docs: add app dependency audit for self-host`.

---

### Task 2: Firebase + Google console setup  — `[USER]`

**Files:**
- Create: `selfhost/docs/firebase-setup.md` (the step-by-step guide the user follows)
- Create: `selfhost/secrets/.gitignore` (contents: `*`)

**Interfaces:**
- Consumes: nothing.
- Produces: the user has a live Firebase project `omi-xuanloi`; the audit doc's "Firebase values" section is filled with real values (web config, service account path, Google OAuth client id/secret, redirect URI).

- [ ] **Step 1: Write the guide**

Write `selfhost/docs/firebase-setup.md` with exact click-paths and links:
1. https://console.firebase.google.com → Add project → name `omi-xuanloi` (disable Analytics).
2. Build → Authentication → Get started → Sign-in method → Google → Enable (email scope default).
3. Build → Firestore Database → Create database → Production mode → region `asia-southeast1`.
4. Project settings → Service accounts → Generate new private key → save `firebase-service-account.json`; later SCP to `/opt/omi/secrets/` (mode 600).
5. Project settings → General → Your apps → Web app (name `omi-desktop`) → copy `apiKey`, `authDomain`, `projectId` into `desktop/windows/.env` (Task 7) and record in the audit doc.
6. https://console.cloud.google.com → project `omi-xuanloi` → APIs & Services → Credentials → Create OAuth client ID → **Desktop app** → record `client_id`/`client_secret`. (These are the backend's Google OAuth creds — same shape `routers/auth.py` expects.)
7. Firestore → Rules → owner-only rules (replace rules file with):
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{uid}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```
(Publish the rules after backend deploy — Firestore must be reachable first; mark step 7 as "after Task 4".)

- [ ] **Step 2: Hand to the user, collect outputs**

The user follows steps 1–6 and reports back: project id, web config values, Google OAuth client id/secret, and confirms the service account JSON is downloaded. Record them in the audit doc's Firebase section (the file is gitignored? no — the audit doc is committed; store real values only in `selfhost/.env.template` as the commit-safe form? **Decision:** real values NEVER go in committed files; they go in `/opt/omi/.env` on the VPS and `desktop/windows/.env` (gitignored) locally. The audit doc's Firebase section holds the FIELD NAMES and placeholders only.)

- [ ] **Step 3: Verify + commit**

Verify the user's project exists by asking them to confirm the console shows the project + Google provider enabled. Commit the guide: `docs: add firebase setup guide for self-host`.

---

### Task 3: VPS prep — `[USER]`

**Files:**
- Create: `selfhost/scripts/vps-prep.sh`
- Create: `selfhost/nginx/omi-api.conf`, `selfhost/nginx/omi-desk.conf`, `selfhost/nginx/omi-ws.conf`
- Create: `selfhost/docs/cloudflare-dns.md`

**Interfaces:**
- Consumes: subdomain names from Global Constraints.
- Produces: VPS ready (swap, n8n limit, nginx vhosts, SSL, DNS) with a recorded baseline RAM measurement.

- [ ] **Step 1: Write vps-prep.sh**

`selfhost/scripts/vps-prep.sh` (run as root on the VPS) containing, verbatim:
```bash
#!/bin/bash
set -euo pipefail
# 1. Swap 2GB
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile
  mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "vm.swappiness=10" >> /etc/sysctl.d/99-omi.conf
  sysctl --system
fi
# 2. n8n memory limit (edit existing compose; idempotent)
COMPOSE=/opt/n8n/docker-compose.yml
if [ -f "$COMPOSE" ] && ! grep -q 'mem_limit' "$COMPOSE"; then
  sed -i '/restart: always/a\    mem_limit: 1g\n    memswap_limit: 1g' "$COMPOSE"
  cd /opt/n8n && docker compose up -d
fi
# 3. Create /opt/omi dirs
mkdir -p /opt/omi/{compose,secrets,data}
chmod 700 /opt/omi/secrets
# 4. Baseline measurement (record output)
free -m
docker stats --no-stream 2>/dev/null | head -20
uptime
echo "VPS_PREP_DONE"
```
- [ ] **Step 2: Write nginx vhosts + DNS doc**

`selfhost/nginx/omi-api.conf`:
```nginx
server {
    listen 80;
    server_name omi-api.xuanloi.me;
    return 301 https://$server_name$request_uri;
}
server {
    listen 443 ssl;
    server_name omi-api.xuanloi.me;
    ssl_certificate /etc/letsencrypt/live/omi-api.xuanloi.me/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/omi-api.xuanloi.me/privkey.pem;
    client_max_body_size 100m;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
    }
}
```
`omi-desk.conf`: same shape → `127.0.0.1:8090`. `omi-ws.conf`: same + WebSocket upgrade headers:
```nginx
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
```
→ `127.0.0.1:8091`.

`selfhost/docs/cloudflare-dns.md`: add A records (DNS only) for the three subdomains → `103.116.39.65`, mirroring the 9router pattern in `D:\Websites\HUONG-DAN-HA-TANG.md` §3.

- [ ] **Step 3: User runs it**

User: `scp selfhost/scripts/vps-prep.sh selfhost/nginx/* root@103.116.39.65:/tmp/ && ssh root@103.116.39.65 "bash /tmp/vps-prep.sh"`, then adds the 3 DNS records in Cloudflare, then `ssh root@103.116.39.65 "certbot --nginx -d omi-api.xuanloi.me -d omi-desk.xuanloi.me -d omi-ws.xuanloi.me"` (follow certbot's interactive prompts).

- [ ] **Step 4: Verify + record**

User runs and reports: `free -m` shows swap; `docker stats` shows n8n mem_limit; `curl -I https://omi-api.xuanloi.me` returns HTTP 502 (nginx up, backend not yet — expected). Append the baseline `free -m` output to the audit doc. Commit the scripts: `chore: add vps-prep scripts and nginx vhosts`.

---

### Task 4: Backend + desktop-backend deploy — `[USER]`

**Files:**
- Create: `selfhost/docker-compose.yml`
- Create: `selfhost/.env.template` (commit-safe placeholders)
- Create: `selfhost/scripts/deploy-backend.sh`

**Interfaces:**
- Consumes: Task 1 (env decisions incl. OpenAI base URL + Deepgram self-hosted vars), Task 2 (Firebase service account), Task 3 (subdomains live).
- Produces: `https://omi-api.xuanloi.me` serving the Python backend; `https://omi-desk.xuanloi.me` serving desktop-backend; authed-curl works.

- [ ] **Step 1: Write docker-compose.yml**

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: always
    mem_limit: 200m
    command: ["redis-server", "--save", "60", "1000"]
    volumes: ["redis_data:/data"]
    networks: [omi]
  backend:
    build: { context: ../../, dockerfile: backend/Dockerfile }
    restart: always
    mem_limit: 1024m
    env_file: /opt/omi/.env
    volumes: ["/opt/omi/secrets:/secrets:ro"]
    ports: ["127.0.0.1:8080:8080"]
    depends_on: [redis]
    networks: [omi]
  desktop-backend:
    build: { context: ../../, dockerfile: backend/Dockerfile.desktop_backend }
    restart: always
    mem_limit: 700m
    env_file: /opt/omi/.env
    volumes: ["/opt/omi/secrets:/secrets:ro"]
    ports: ["127.0.0.1:8090:8080"]
    networks: [omi]
  pusher:
    build: { context: ../../backend, dockerfile: pusher/Dockerfile }
    restart: always
    mem_limit: 800m
    env_file: /opt/omi/.env
    ports: ["127.0.0.1:8091:8080"]
    depends_on: [redis]
    networks: [omi]
networks: { omi: {} }
volumes: { redis_data: {} }
```
(Dockerfile paths verified in the repo: `backend/Dockerfile`, `backend/Dockerfile.desktop_backend`, `backend/pusher/Dockerfile` with build context `../../backend` — the compose above already matches; `backend/pusher/Dockerfile` exists at `backend/pusher/`.)

- [ ] **Step 2: Write .env.template**

From `backend/.env.template` + the Task 1 decisions, with every value either a placeholder or a fixed choice:
```
MEMORY_ENABLED=on
BUCKET_SPEECH_PROFILES=
BUCKET_BACKUPS=
GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase-service-account.json
FIREBASE_API_KEY=<web-config>
FIREBASE_AUTH_DOMAIN=<web-config>
FIREBASE_PROJECT_ID=omi-xuanloi
SERVICE_ACCOUNT_JSON=
REDIS_DB_HOST=redis
REDIS_DB_PORT=6379
REDIS_DB_PASSWORD=
OPENAI_API_KEY=<9router-key>
<OPENAI-BASE-URL-VAR>=https://9router.xuanloi.me/v1
DEEPGRAM_SELF_HOSTED_ENABLED=1
DEEPGRAM_SELF_HOSTED_URL=<stt-adapter internal URL, filled in Task 6>
HOSTED_PUSHER_API_URL=http://pusher:8080
ENCRYPTION_SECRET=<openssl rand -hex 32>
ADMIN_KEY=<openssl rand -hex 16>
ADMIN_KEY_AUTH_ENABLED=true
CORS_ALLOWED_ORIGINS=<app origin>
GOOGLE_CLIENT_ID=<oauth-client-id>
GOOGLE_CLIENT_SECRET=<oauth-client-secret>
BASE_API_URL=https://omi-api.xuanloi.me
API_BASE_URL=https://omi-api.xuanloi.me
POSTHOG_PROJECT_API_KEY=
ELEVENLABS_API_KEY=
PERPLEXITY_API_KEY=
TWILIO_ACCOUNT_SID=
STRIPE_API_KEY=
```
Replace `<OPENAI-BASE-URL-VAR>` with the exact var from Task 1 Step 3; if the backend hardcodes the OpenAI endpoint, add the audit's chosen override mechanism instead. `HOSTED_PUSHER_API_URL` and `DEEPGRAM_SELF_HOSTED_URL` use Docker-network service names.

- [ ] **Step 3: Write deploy-backend.sh**

```bash
#!/bin/bash
set -euo pipefail
cd /opt/omi/compose
cp -n /tmp/omi/.env /opt/omi/.env 2>/dev/null || true   # user supplies the real .env (mode 600)
docker compose build
docker compose up -d redis backend desktop-backend
docker compose ps
```
The user fills `/opt/omi/.env` with real values (from the template + Task 2 outputs), SCPs the repo (or `git clone` the fork on the VPS), and runs it.

- [ ] **Step 4: Verify**

User runs and reports:
- `curl -s https://omi-api.xuanloi.me/v1/health` → 200 (route verified at `backend/routers/other.py:8`).
- Authed call using the documented `ADMIN_KEY<uid>` bypass to a protected route → 200 with data.
- `curl -s https://omi-desk.xuanloi.me/health` and `/ready` → 200 (routes at `backend/routers/desktop_core.py:77,82`).
Record outputs in the audit doc. Commit: `feat: add self-host backend compose + env template + deploy script`.

---

### Task 5: Pusher + Redis live — `[USER]`

**Files:**
- Modify: `selfhost/docker-compose.yml` (already includes pusher/redis)
- Create: `selfhost/scripts/deploy-pusher.sh`

**Interfaces:**
- Consumes: Task 4 (backend up, `HOSTED_PUSHER_API_URL`).
- Produces: `om  -ws.xuanloi.me` serving the pusher WS; Redis reachable from backend.

- [ ] **Step 1: Write deploy-pusher.sh**

```bash
#!/bin/bash
set -euo pipefail
cd /opt/omi/compose
docker compose up -d pusher
docker compose ps
docker exec $(docker compose ps -q redis) redis-cli ping
```

- [ ] **Step 2: User runs + verifies**

Report: `redis-cli ping` → `PONG`; `curl -s https://omi-ws.xuanloi.me/` returns the pusher's HTTP response (non-5xx); backend logs show pusher connectivity (no `HOSTED_PUSHER` errors). Record in audit doc. Commit if compose changed: `chore: enable pusher service`.

---

### Task 6: STT adapter — sherpa-onnx (Deepgram-compatible)

**Files:**
- Create: `selfhost/stt-adapter/main.py`
- Create: `selfhost/stt-adapter/recognizer.py`
- Create: `selfhost/stt-adapter/protocol.py`
- Create: `selfhost/stt-adapter/Dockerfile`
- Create: `selfhost/stt-adapter/requirements.txt`
- Create: `selfhost/stt-adapter/tests/test_protocol.py`
- Test: `selfhost/stt-adapter/tests/fixtures/sample-vi.wav` (generated)

**Interfaces:**
- Consumes: Task 1 Step 3's pinned Deepgram self-hosted protocol contract (message JSON + binary framing + sample rate). The recognizer wrapper:
  - `class ViRecognizer` with `def __init__(model_dir: str, num_threads: int = 2)` and `def transcribe_chunk(pcm: bytes) -> list[dict]` returning `[{text, is_final}]`.
  - `def load_model(url_or_dir: str) -> str` returning the local model dir.
- Produces: a Docker image `omi-stt-adapter` serving a FastAPI WebSocket at `/v1/stream` speaking the pinned Deepgram subset; backend `DEEPGRAM_SELF_HOSTED_URL=http://stt-adapter:8092` (added to compose).

- [ ] **Step 1: Write the failing protocol test**

`selfhost/stt-adapter/tests/test_protocol.py`:
```python
import asyncio, json
import pytest
from fastapi.testclient import TestClient
from main import app

def test_start_results_close_handshake():
    client = TestClient(app)
    with client.websocket_connect("/v1/stream") as ws:
        ws.send_text(json.dumps({"type": "Start",
            "encoding": "linear16", "sample_rate": 16000, "channels": 1,
            "interim_results": True}))
        # server must acknowledge with a Start-complete result or a Ready msg
        first = json.loads(ws.receive_text())
        assert first["type"] in ("Ready", "Results")
        ws.send_text(json.dumps({"type": "CloseStream"}))
        last = json.loads(ws.receive_text())
        assert last["type"] == "Results" or last["type"] == "CloseStream"
```
(Run against a recognizer stub; the exact message types are per Task 1's pin — adjust the asserts to the pinned contract and note the source.)

- [ ] **Step 2: Run — expect FAIL**

`cd selfhost/stt-adapter && python -m pytest tests/test_protocol.py -v` (or via the repo's uv env). Expected: import error (main.py missing).

- [ ] **Step 3: Implement recognizer.py**

Wrap `sherpa-onnx` `OnlineRecognizer` with the `zipformer-vi-30M-int8-2026-02-09` model. `load_model()` downloads and extracts the tarball on first run from the pinned URL:
`https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2`
into `MODEL_DIR` (volume `stt_models`). `transcribe_chunk` feeds PCM to `recognizer.accept_waveform`, drains `recognizer.get_result()` + endpointing, returns final+interim segments.

- [ ] **Step 4: Implement protocol.py + main.py**

`protocol.py`: encode/decode the pinned Deepgram subset (Start → init recognizer with the connection's config; raw PCM binary frames → `transcribe_chunk`; `CloseStream` → flush finals). `main.py`: FastAPI app with `@app.websocket("/v1/stream")` using `ViRecognizer`, plus a `/health` GET. No auth (internal Docker network only).

- [ ] **Step 5: Wire into compose + run tests**

Add to `selfhost/docker-compose.yml`:
```yaml
  stt-adapter:
    build: { context: ./stt-adapter }
    restart: always
    mem_limit: 500m
    ports: ["127.0.0.1:8092:8092"]
    volumes: ["stt_models:/models"]
    networks: [omi]
```
Set `DEEPGRAM_SELF_HOSTED_URL=http://stt-adapter:8092` in `/opt/omi/.env`. Run `python -m pytest tests/ -v` — expect GREEN. Then smoke-test the recognizer with REAL speech: record ~10s of Vietnamese speech in the app (Task 8) and copy the WAV (or use a public Vietnamese speech sample) into `tests/fixtures/sample-vi.wav`; run the recognizer on it and confirm it returns a non-empty Vietnamese hypothesis without error. (A synthetic sine tone is NOT a valid speech fixture — the recognizer must see real speech.)

- [ ] **Step 6: Commit**

`git add selfhost/stt-adapter && git commit -m "feat: add sherpa-onnx Vietnamese STT adapter (Deepgram-compatible)"`

---

### Task 7: App wiring — `[USER]` for sign-in

**Files:**
- Modify: `desktop/windows/.env` (gitignored — local only)
- Create: `selfhost/docs/app-env.md`

**Interfaces:**
- Consumes: Task 2 web config + Task 4 subdomains.
- Produces: the app runs against the new Firebase + backends; user can sign in with a fresh Google account.

- [ ] **Step 1: Write app-env.md + set .env**

`selfhost/docs/app-env.md` documents the 7 env changes (Global Constraints). Apply them to `desktop/windows/.env`:
```
VITE_FIREBASE_API_KEY=<new project apiKey>
VITE_FIREBASE_AUTH_DOMAIN=<new project authDomain>
VITE_FIREBASE_PROJECT_ID=omi-xuanloi
VITE_OMI_API_BASE=https://omi-api.xuanloi.me
VITE_OMI_DESKTOP_API_BASE=https://omi-desk.xuanloi.me
VITE_OMI_API_KEY=
VITE_POSTHOG_KEY=
MAIN_VITE_GOOGLE_CLIENT_ID=<backend oauth client id>
VITE_ENABLE_GOOGLE_INTEGRATION=0
```

- [ ] **Step 2: Dev run + sign-in**

`C:\Omi\.node22\pnpm.cmd run dev` (with `OMI_SANDBOX=dev1`) → app opens → user clicks Google sign-in → completes against the NEW Firebase project. Confirm the sign-in log shows the new auth domain.

- [ ] **Step 3: Generate dev API key + record**

User: Settings → Developer → create API key (uses the new backend) → set `VITE_OMI_API_KEY` → restart dev → confirm cloud-sync works (a recorded conversation syncs to the new Firestore). Commit the doc: `docs: add self-host app env guide`.

---

### Task 8: E2E verification — `[USER]` drives the app

**Files:**
- Create: `selfhost/docs/verification-checklist.md`

**Interfaces:**
- Consumes: all prior tasks live.
- Produces: acceptance evidence recorded.

- [ ] **Step 1: Write the checklist**

`selfhost/docs/verification-checklist.md` with the spec's acceptance items as checkboxes:
1. `curl /health` → 200 (both backends).
2. Authed `ADMIN_KEY<uid>` curl to a data route → 200.
3. App: record a ~20s screen+mic session → transcript appears (Vietnamese STT via sherpa) → conversation saved to new Firestore (`users/{uid}/conversations`).
4. Ask the agent a question in chat → answered (9Router LLM) → memory extraction writes a `users/{uid}/memories` doc (MEMORY_ENABLED=on).
5. `docker compose restart` on the VPS → app reconnects; data persists; no crash loops (`docker compose ps`, logs clean).
6. `free -m` stays < 3.5GB with swap mostly untouched.

- [ ] **Step 2: Run it with the user**

Execute items 1–2 (user runs curl), 3–4 (user records in the app and reports transcript/chat results), 5–6 (user runs on VPS). Fill in pass/fail per item; if any fails, fix forward (deploy fix → re-verify that item only).

- [ ] **Step 3: Commit**

`git add selfhost/docs/verification-checklist.md && git commit -m "docs: record self-host E2E verification results"`

---

### Task 9: Documentation — `[USER]` owns D:\Websites, agent drafts

**Files:**
- Modify: `D:\Websites\HUONG-DAN-HA-TANG.md` (user's infra doc — agent drafts the diff, user applies)
- Modify: `desktop/windows/README.md`

**Interfaces:**
- Consumes: the deployed reality from Tasks 4–8.
- Produces: ops docs matching the live system.

- [ ] **Step 1: Draft HUONG-DAN-HA-TANG.md updates**

Append to the VPS section: new services table (`omi-api/omi-desk/omi-ws` → ports 8080/8090/8091, Docker at `/opt/omi/compose`), new subdomains in §3 DNS, restart commands (`cd /opt/omi/compose && docker compose up -d`), log commands (`docker compose logs -f backend`), and the `/opt/omi/.env` secret location note. Present the diff to the user to apply to `D:\Websites\HUONG-DAN-HA-TANG.md` (that file is outside the repo — user applies; agent must NOT edit it directly without the user's confirmation).

- [ ] **Step 2: Update desktop/windows/README.md**

Add a `## Self-hosted backend` section: the 7 env vars, the subdomain layout, and a pointer to `selfhost/docs/*`.

- [ ] **Step 3: Commit**

`git add desktop/windows/README.md && git commit -m "docs: document self-hosted backend setup"`
