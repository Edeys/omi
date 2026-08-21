# Omi Self-Host — App Dependency Audit

> **Date:** 2026-08-21
> **Branch:** `feat/selfhost-backend`
> **Scope:** Windows app at `C:/Omi/desktop/windows` vs two backends — `VITE_OMI_API_BASE` (Python backend, `backend/main.py`) and `VITE_OMI_DESKTOP_API_BASE` (desktop backend, `backend/desktop_backend.py` + pusher). Repo commit baseline `ccd6230`.
> **Method:** Grep of Windows sources listed in the brief + broader `desktop/windows/src` for `omiApi`/`desktopApi`/`fetch`/`axios` + read of backend `utils/llm/clients.py`, `utils/stt/streaming.py`, `config/stt_provider_policy.py`, `database/_client.py`, `utils/env_loader.py`, `routers/auth.py`, `utils/other/endpoints.py`, `routers/other.py`, `routers/desktop_core.py`, `pusher/main.py`, `utils/llm/providers.py`, Dockerfiles.
> **Purpose:** Authoritative endpoint + env table every later self-host task cites. No source changes — read-only.

---

## 1. Python backend surface — `VITE_OMI_API_BASE`

Base is resolved in `desktop/windows/src/main/ipc/auth.ts:25`, `byok.ts:25`, `mcpExports.ts:54` as `import.meta.env.VITE_OMI_API_BASE || 'https://api.omi.me'`. All `omiApi` clients in `renderer/src/lib/apiClient.ts:152` and raw `fetch` callers use this base. Axios timeout 12s (`apiClient.ts:124`), platform headers `X-App-Platform: windows`, `X-Device-Id-Hash`, `X-App-Version` (`apiClient.ts:106,142-143`), Firebase `Authorization: Bearer <id_token>` (`apiClient.ts:132-134`), BYOK `X-BYOK-*` when active (`apiClient.ts:137-141`).

| # | Endpoint | Method | Where in Windows app (file:line) | Purpose | Needed for **core** (listen+chat+memory)? | Degraded behavior if missing / 404 / 5xx |
|---|----------|--------|-----------------------------------|---------|---------------------------------------------|-------------------------------------------|
| 1 | `/v2/messages` (+ `?app_id=`) | `POST` (SSE streaming, `fetch` + `text/event-stream`) | `renderer/src/hooks/useChat.ts:1175-1178` (legacy_sse path), `renderer/src/lib/agentLLM.ts:21-22` (planner fallback) | **Conversational chat — primary LLM turn** (typed bar, fallback when `desktopApi` 429). Server streams SSE `done:` with citations. | **YES** — core chat when `chatEngine='legacy_sse'` or desktop backend down. Pi-mono preferred but this is fallback. | Chat send fails with `friendlyChatError`; no memory. Spec: falls back to `/v2/messages` on 429 (`agentLLM.ts:38-43`). Self-host must implement or chat dead when desktop down. |
| 2 | `/v2/files` | `POST` multipart (`files` field) | `renderer/src/lib/chatAttachmentUpload.ts:47` (`fetch(`${OMI_BASE}/v2/files`)`) | Upload chat attachments; returns `FileChat.id` for next `file_ids`. | No | Attachment fails, text send proceeds (`useChat.ts:1016-1018` aborts only when all uploads failed + no text). |
| 3 | `/v2/desktop/messages` | `POST` (JSON) | `renderer/src/lib/desktopChatMessages.ts:39`, `hooks/useChat.ts:689,961` (`saveDesktopMessage`) | Pi-mono persistence to shared/mobile thread (`plugin_id==None` continuity). Fire-and-forget. | **YES for pi_mono core** — legacy_sse gets continuity server-side; pi_mono must call or history local-only. | `saveDesktopMessage` catches returns `null` (`desktopChatMessages.ts:41-42`); no UI error but shared thread diverges. |
| 4 | `/v2/desktop/messages` | `GET` | `renderer/src/lib/chatSessionsClient.ts:204` | Read persisted messages for session / shared thread. | No — session history view. | “Load thread” empty. |
| 5 | `/v2/desktop/messages` | `DELETE` | `chatSessionsClient.ts:214` | Bulk-delete thread messages. | No | Delete fails, messages remain. |
| 6 | `/v2/chat-sessions` | `POST` | `chatSessionsClient.ts:139` | Create desktop-local chat session. | No | New chat falls back to shared thread. |
| 7 | `/v2/chat-sessions` | `GET` | `chatSessionsClient.ts:151` | List sessions. | No | Session list empty. |
| 8 | `/v2/chat-sessions/{id}` | `GET` | `chatSessionsClient.ts:157` | Fetch one session. | No | Stays on shared thread. |
| 9 | `/v2/chat-sessions/{id}` | `PATCH` | `chatSessionsClient.ts:170` | Rename / star toggle. | No | Edit silently fails. |
| 10 | `/v2/chat-sessions/{id}` | `DELETE` | `chatSessionsClient.ts:180` | Delete session (cascade). | No | Session remains. |
| 11 | `/v1/conversations/from-segments` | `POST` | `renderer/src/lib/sync/outbox.ts:36`, `conversationSync.ts:48` | **Screen recording → cloud conversation.** Body: `transcript_segments[], started_at, finished_at, language, source:'desktop', client_platform:'windows', client_session_id` (`outbox.ts:86-99`). Rate-limit 30/h. Client-owned idempotency via `started_at/finished_at` dedupe. | **YES — core `listen`→`memory` for screen** (mic+system). Mic-only via live WS. | `HTTP error → failed` (safe re-post), `timeout → unconfirmed` (dedupe via `GET /v1/conversations` before retry). Row stays pending/failed/unconfirmed, retry on `Conversations` mount (`conversationSync.ts:167-173`). Self-host must implement or recordings stay `local_only`. |
| 12 | `/v1/conversations` | `GET` (`?limit=30&offset=0`) | `conversationSync.ts:59-61` | List recent conversations (dedupe + context). | **YES for dedupe** | `unconfirmed` stays forever. Assistants degrade to `[]`. |
| 13 | `/v1/auth/authorize` | `GET` (`?provider=google|apple&redirect_uri&state&code_challenge&code_challenge_method=S256`) | `main/auth/omiAuth.ts:37`, `signInFlow.ts:165-166` | Start backend-mediated OAuth (PKCE S256, loopback `http://127.0.0.1:<port>/callback`). 302 to provider. | **YES — sign-in** | Sign-in shows “Could not open browser” / timeout (`signInFlow.ts:178-184`). App stays signed-out. |
| 14 | `/v1/auth/token` | `POST` `application/x-www-form-urlencoded` (`grant_type=authorization_code&code&redirect_uri&use_custom_token=true&code_verifier`) | `main/auth/omiAuth.ts:143` | Exchange loopback `code` for Firebase `custom_token` + `id_token`. | **YES — sign-in** | Token exchange fails (`Token exchange failed (4xx)` `omiAuth.ts:148-156`); sign-in logs and returns `{ok:false}`. |
| 15 | `/v1/users/me/byok-active` | `POST` `{fingerprints}` | `main/agentKernel/byokEnroll.ts:32,43-54` | Enroll BYOK free plan (SHA-256 fingerprints, not raw keys). Must not carry `X-BYOK-*`. | No | Settings shows “enroll failed”; keys stay local but backend 403 if enrolled mismatch. |
| 16 | `/v1/users/me/byok-active` | `DELETE` | `byokEnroll.ts:60-75` | Deactivate BYOK on sign-out / incomplete set. Best-effort. | No | Stays enrolled with stale fingerprints → 403 without `X-BYOK-*` (`byokEnroll.ts:120`). Mitigated by TTL. |
| 17 | `/v1/mcp/keys` | `POST` `{name}` | `main/mcp/mcpMintClient.ts:59`, `mcpExportsService.ts:42` | Mint hosted MCP key. | No | Connections connect fails; manual copy fallback (`mcpExports.ts:123`). |
| 18 | `/v1/mcp/keys` | `GET` | `mcpMintClient.ts:76` | List hosted MCP keys (metadata). | No | Status “available” not “connected”. |
| 19 | `/v1/mcp/keys/{id}` | `DELETE` | `mcpMintClient.ts:97` | Revoke/rotate hosted key. | No | Old key stays alive (best-effort `mcpExportsService.ts:73-75`). |
| 20 | `/v2/desktop/update-feed/windows` | `GET` `?channel=stable|beta` → `{requested_channel,served_channel,feed_url}` | `main/windowsUpdateFeed.ts:55-64` | Resolve immutable Windows release feed URL (`https://github.com/.../releases/download/vX-windows/`). Then `electron-updater` fetches `latest.yml`. | No | See §3c — non-ok throws, caught as non-fatal warning, no update staged. |
| 21 | `/v1/x/connection-status` | `GET` | `main/integrations/xConnector.ts:60` via `xSession.ts:12` | X (Twitter) connector check. | No | X panel “not connected”. |
| 22 | `/v1/x/oauth-url` | `GET` | `xConnector.ts:78` | Get X OAuth URL. | No | “Connect X” fails. |
| 23 | `/v1/x/sync` | `POST` | `xConnector.ts:91` | Trigger X sync. | No | Manual sync errors. |
| 24 | `/v1/x/disconnect` | `POST` | `xConnector.ts:101` | Disconnect X. | No | Stays connected. |
| 25 | `/v3/memories` `POST`/`GET`/`DELETE`/`PATCH`, `POST /v3/memories/batch`, `GET/POST/DELETE /v1/knowledge-graph`, `POST /v1/memories/extract`, `POST /v1/connectors/synthesize`, `GET /v1/users/me/subscription|usage-quota|trial`, `POST /v1/payments/*`, `GET /v1/apps`, `POST /v1/goals`, `GET /v1/conversations/topic`, etc. | Various | `hooks/useMemories.ts:70,158,193`, `lib/memoriesBulk.ts:41,81,124`, `lib/knowledgeGraphClient.ts:7,13,19`, `lib/memoryExtract.ts:39-40`, `lib/billing.ts:27,35,39,43,533-546`, `lib/chatApps.ts:42`, `lib/goals.ts:54` — **not in brief’s grep list but reachable via same `omiApi` base** | Memories, KB, billing, apps, goals — all **non-core** per spec non-goals / degraded-acceptable. | See §4 — each fails open (empty list / toast / paywall UI) and never blocks listen+chat+memory. Row aggregates sprawl; `grep -R 'omiApi\.'` can expand to one row per path. |
| 26 | **WS** `wss://…/v4/listen?language=&sample_rate=16000&codec=pcm16&channels=1&include_speech_profile=true&source=desktop&speaker_auto_assign=enabled&client_conversation_id=&uid=` | WS upgrade, `Authorization: Bearer <token>` + `X-App-Platform: windows`, `X-Device-Id-Hash`, `X-BYOK-*` when active | `main/ipc/omiListen.ts:67-95` (`buildListenEndpoint`), `buildListenHeaders:181-187`, `byokSttHeaders:31-39` | **Live mic → STT + diarizer + pusher pipeline** (continuous). Binary `linear16` frames → server sends `segments[]` and event JSON. Keepalive `b'\x00'*320` every 30s (`omiListen.ts:117`), watchdog stale 60s (`omiListen.ts:134`). | **YES — core `listen`** | WS `error`/`close` emits to renderer; `liveMicSession` retries then rescues via `from-segments` (`capture/liveRescue.ts`). UI “reconnecting…”. Spec: “STT failure → retries/fails with clear error; pusher stays up”. |
| 27 | **WS** `wss://…/v2/voice-message/transcribe-stream?language=&sample_rate=16000&codec=linear16&channels=1` | WS, header-auth only (no `uid` query — `omiListen.ts:326`) | `omiListen.ts:73-80` | Transcription-only STT for **PTT** and **screen** mic+system lanes. Expects `linear16` (rejects `pcm16` with 1008). Renderer sends `finalize` to flush (`omiListen.ts:504`). | **YES for PTT + screen lanes** | Same rescue path as #26 for exhausted case (`liveMicSession.ts:126`). |

> **Note on non-core `omiApi` sprawl:** The Windows app imports `omiApi` in >30 modules; a full `grep 'omiApi\.(get|post|patch|delete)'` yields ~80 call sites. The table above pins *every* call site the brief explicitly lists. Row 25 aggregates remaining `omiApi` users and marks them non-core per spec §Degradation / §Non-Goals.

---

## 2. Desktop backend surface — `VITE_OMI_DESKTOP_API_BASE`

Base resolved as `import.meta.env.VITE_OMI_DESKTOP_API_BASE || 'https://desktop-backend-hhibjajaja-uc.a.run.app'` in `renderer/src/lib/geminiClient.ts:27`, `main/codingAgent/piMonoSession.ts:109` (`piMonoManagedApiBaseUrl`), `main/automation/planner.e2e.test.ts:49`.

| # | Endpoint | Method | Where in Windows app (file:line) | Purpose | Needed for core? | Degraded behavior if missing |
|---|----------|--------|-----------------------------------|---------|------------------|------------------------------|
| D1 | `/v2/chat/completions` | `POST` `{model, stream, messages, tools, tool_choice, ...}` → OpenAI-compatible SSE / JSON | `renderer/src/lib/agentLLM.ts:31-32` (`desktopApi.post('/v2/chat/completions')`), `renderer/src/lib/localAgent.ts:131`, `main/automation/planner.e2e.test.ts:113-114`, **pi-mono** subprocess: `main/codingAgent/piMono.ts:549-550` (`env.OMI_API_BASE_URL = ${desktopApiBase}/v2`) → pi `POST <OMI_API_BASE_URL>/chat/completions` | **YES when `chatEngine='pi_mono'` (default, `appSettings.ts:136`)** — managed-cloud chat path. Legacy `agentLLM.ts:38-43` falls back to `/v2/messages` on 429/Network, so not hard dependent, but self-host plans pi_mono as primary. | `desktopApi.post` 429 → `callAgentLLM` falls back to `callViaMessages` (`/v2/messages`) (`agentLLM.ts:42-43`); other errors throw and surface as `friendlyChatError`. In `useChat:tryKernelChat` (`hooks/useChat.ts:648-974`) retries 1-3 with backoff then “busy” copy. No crash. |
| D2 | `/v1/proxy/gemini/models/{model}:generateContent` | `POST` `{contents:[{role, parts}], systemInstruction?, generationConfig:{responseMimeType, responseSchema, thinkingConfig}}` | `renderer/src/lib/geminiClient.ts:28,48-54`, `main/assistants/*` (`aiUserProfile/synthesis.ts:4`, `goals/generate.ts:112-113`, `focus/gemini.ts:117-118`, `memory/gemini.ts:113-114`, `insight/gemini.ts:199-200`, `tasks/geminiWire.ts:199-200`) | Gemini proxy — desktop backend injects real `GEMINI_API_KEY` / Vertex, proxies to `generativelanguage.googleapis.com`. Used for AI User Profile, goals, focus/advice, memory insight, task planning — all main-process assistants. Renderer `geminiClient.generate` retries 429/503 twice (`geminiClient.ts:62-65`). | No — all **non-core assistants**. Spec §Non-Goals lists these as not needed for “listen + execute commands”. | Assistant timer logs warning and skips generation until next tick (e.g. `aiUserProfile/orchestrate.ts:106`, `goals/generate.ts:374` throws, caller treats as retryable). No user-visible error except stale assistant features. |
| D3 | `/v1/proxy/gemini/models/gemini-embedding-001:embedContent` | `POST` `{model:'models/gemini-embedding-001', content:{parts:[{text}]}, taskType}` | `main/rewind/embeddingClient.ts:55,96-103` | Single embedding (search query). Part of Rewind screen-activity indexer. | No | Search over screen history no results; logs `embedding proxy request failed` and retries (`embeddingClient.ts:76,84`). |
| D4 | `/v1/proxy/gemini/models/gemini-embedding-001:batchEmbedContents` | `POST` `{requests: [...] <=100}` | `main/rewind/embeddingClient.ts:55,131-132` | Batch embeddings for stored OCR text (`RETRIEVAL_DOCUMENT`). Chunked at 100 (`embeddingClient.ts:112`). | No | Batch indexer stalls, re-queues; same retry as D3. |
| D5 | `/health` + `/ready` | `GET` | Not called by Windows app; used by self-host health checks / LB. `routers/desktop_core.py:77-78` (`@router.get('/health')`) and `:82` (`/ready`) | Liveness vs readiness (Redis). | N/A (infra) | LB routes away from unready pod; chat 503 until ready. |
| D6 | `/v1/config/api-keys` | `GET` | Not called by Windows app today (listed `desktop_core.py:95-105`), but available for debugging. | Returns `firebase_api_key`, `google_calendar_api_key`, `anthropic_api_key` from env. | No | N/A. |

Desktop backend also hosts `POST /v1/webhooks/sentry`, `GET /v1/webhooks/sentry/poll`, `POST /v1/realtime/*`, `desktop_agent_vm`, `desktop_tts_updates`, `desktop_screen_crisp`, `desktop_proactivity` — none is called by the Windows app today (grep `desktopApi|VITE_OMI_DESKTOP` hits only D1-D4 paths plus `/v1/proxy/gemini`).

---

## 3. Backend env decisions — with `file:line` evidence

### 3a. LLM base URL wiring — exact env var + 9Router path

**Finding: no `OPENAI_BASE_URL` / `OPENAI_API_BASE` env var exists. OpenAI base URL is hardcoded to OpenAI default via `langchain_openai.ChatOpenAI` default; only OpenRouter and Gemini have explicit `base_url`s. The 9Router gateway must be wired via an override or gateway lane.**

Evidence:

- `backend/utils/llm/providers.py:30` — `GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"` (only Gemini BYOK).
- `backend/utils/llm/providers.py:44-53` — `OPENAI_COMPATIBLE_PROVIDERS`:
  ```python
  'openai': OpenAICompatibleProviderConfig(name='openai', api_key_env='OPENAI_API_KEY'),  # ← no base_url
  'openrouter': OpenAICompatibleProviderConfig(
      name='openrouter', api_key_env='OPENROUTER_API_KEY',
      base_url="https://openrouter.ai/api/v1",
  )
  ```
- `backend/utils/llm/providers.py:109` — `api_key = os.environ.get(provider_config.api_key_env)` (only key is read, never `*_BASE_URL`).
- `backend/utils/llm/providers.py:124` — `ChatOpenAI(..., **kwargs)` where `kwargs['base_url']` set only when `provider_config.base_url` truthy — never for `openai`.
- `backend/.env.template:54` — only `OPENAI_API_KEY=` (no base URL).
- `backend/utils/llm/clients.py:390-408` — `_create_byok_client` for `openai` does `ChatOpenAI(model, api_key=byok_key, **kwargs)` with no `base_url`.
- Grep `OPENAI_BASE_URL|OPENAI_API_BASE|base_url` env read across `backend/` — **zero hits**.

**Decision for self-host (9Router at `https://9router.xuanloi.me/v1`, OpenAI-compatible):**

Recommended self-host patch (minimal, keeps secret in `/opt/omi/.env` mode 600):

1. Add optional override envs (no change when unset — preserves cloud `api.openai.com`):
   - `OPENAI_BASE_URL` (preferred) and/or `OPENROUTER_BASE_URL`.
   - In `backend/utils/llm/providers.py:113-115`, before `ChatOpenAI` construction:
     ```python
     if not provider_config.base_url:
         env_base = os.environ.get('OPENAI_BASE_URL') or os.environ.get('OPENAI_API_BASE')
         if env_base:
             kwargs['base_url'] = env_base.strip().rstrip('/')
     else:
         env_base = os.environ.get('OPENROUTER_BASE_URL')
         if env_base:
             kwargs['base_url'] = env_base.strip().rstrip('/')
     ```
   Then self-host compose sets `OPENAI_API_KEY=<9Router key>` and `OPENAI_BASE_URL=https://9router.xuanloi.me/v1` (and `OPENROUTER_API_KEY` blank). Chat features whose provider resolves to `openai` now go to 9Router.

2. Alternative without code change (fragile, not recommended): set `OPENROUTER_API_KEY=<9Router key>` and run a tiny local reverse proxy `127.0.0.1:8099` that forwards `https://openrouter.ai/api/v1/*` → `https://9router.xuanloi.me/v1/*`. Fragile — must rewrite `Host` and `X-Title` headers (`providers.py:50`).

3. Gateway lane: set `OMI_LLM_GATEWAY_URL=https://9router.xuanloi.me/v1` + `OMI_LLM_GATEWAY_FEATURE_MODE=gateway` + `OMI_LLM_CHAT_AGENT_ROUTE=gateway`. Then `backend/utils/llm/providers.py:128-172` (`get_or_create_omi_gateway_llm`) routes via `GatewayContextChatOpenAI`. Heavier than direct `OPENAI_BASE_URL` patch.

Until the 5-line `OPENAI_BASE_URL` patch lands, setting only `OPENAI_API_KEY=9router-key` still hits `api.openai.com` and fails.

---

### 3b. Deepgram self-hosted — exact env var set + wire contract

**Full `DEEPGRAM_SELF_HOSTED_*` env var set (with file:line):**

- `backend/utils/stt/streaming.py:580` — `is_dg_self_hosted = os.getenv('DEEPGRAM_SELF_HOSTED_ENABLED', '').lower() == 'true'` — boolean gate; `'true'` case-insensitive, else hosted.
- `backend/utils/stt/streaming.py:614-616` inside `_build_managed_deepgram_client()` when `is_dg_self_hosted`:
  ```python
  endpoint = _require_self_hosted_deepgram_endpoint(os.getenv('DEEPGRAM_SELF_HOSTED_URL') or '')
  return DeepgramClient(os.getenv('DEEPGRAM_API_KEY') or '', _deepgram_options(endpoint))
  ```
- `backend/utils/stt/streaming.py:595-604` — `_require_self_hosted_deepgram_endpoint` rejects empty and `api.deepgram.com`.
- So the trio is `DEEPGRAM_SELF_HOSTED_ENABLED=true` (required), `DEEPGRAM_SELF_HOSTED_URL=<self-hosted STT HTTP/WS base, NOT https://api.deepgram.com>` (required, fails closed), `DEEPGRAM_API_KEY=<key self-hosted expects; may be dummy>` (reused, not `DEEPGRAM_SELF_HOSTED_API_KEY`). BYOK `get_byok_key('deepgram')` is ignored when `is_dg_self_hosted` (`streaming.py:784-801`).

Optional self-hosted tuning: no `DEEPGRAM_SELF_HOSTED_WS_URL` — SDK derives WS from HTTP base via `DeepgramClientOptions(url=endpoint)` (`streaming.py:585-592`). Adapter must expose Deepgram-compatible `listen.websocket.v("1")` under `DEEPGRAM_SELF_HOSTED_URL` (e.g. `http://stt-adapter:8092`).

**Exact Deepgram streaming protocol surface the backend consumes (quote relevant code):**

Backend uses `deepgram-sdk` (`from deepgram import DeepgramClient, LiveTranscriptionEvents`, `from deepgram.clients.live.v1 import LiveOptions`) and wraps in `STTSocket`.

`LiveOptions` built in `backend/utils/stt/streaming.py:841-856`:

```python
options = LiveOptions(
    punctuate=True,
    no_delay=True,
    endpointing=300,          # 300 ms — finalized chunks mid-stream
    language=language,        # e.g. 'en', 'vi', 'multi'
    interim_results=False,    # only final results
    smart_format=True,
    profanity_filter=False,
    diarize=True,             # → word.speaker
    filler_words=should_preserve_filler_words(language),
    channels=channels,        # 1 (mono)
    multichannel=channels > 1,
    model=model,              # e.g. 'nova-3'
    sample_rate=sample_rate,  # 16000
    encoding='linear16',      # PCM16 LE mono
)
if keywords:
    options = _dg_keywords_set(options, keywords)  # nova-3 → keyterm else keywords (775-781)
result = dg_connection.start(options)  # 864
```

Transport: binary `linear16` PCM16 LE mono 16kHz 1ch via `STTSocket.send(data: bytes)` / `dg_connection.send(data)`. Windows feed: `omiListen.ts:474 ws.send(pcm)` where `pcm` is 16-bit mono 16kHz from `getUserMedia`.

Message JSON shape consumed `streaming.py:662-696` (`on_message`):

```json
{
  "channel": {
    "alternatives": [{
      "transcript": "hello world",
      "words": [
        {"punctuated_word": "hello", "start": 0.12, "end": 0.34, "speaker": 0},
        {"punctuated_word": "world", "start": 0.40, "end": 0.61, "speaker": 0}
      ]
    }]
  }
}
```

Backend coalesces by `word.speaker` into `{'speaker': f"SPEAKER_{word.speaker}", 'start': word.start, 'end': word.end, 'text': word.punctuated_word, 'is_user': False, 'person_id': None}` (lines 681-694). Empty transcript short-circuits.

Events: `LiveTranscriptionEvents.Transcript`, `Error`, `Open`, `Metadata`, `SpeechStarted`, `UtteranceEnd`, `Close`, `Unhandled` (`streaming.py:814-840`).

**STT adapter contract (sherpa-onnx):** Must expose WS that speaks exactly the Deepgram Live v1 JSON above and accepts `linear16` binary at 16kHz mono. Backend constructs `DeepgramClient(api_key, DeepgramClientOptions(url=DEEPGRAM_SELF_HOSTED_URL))` — so HTTP base must be `DEEPGRAM_SELF_HOSTED_URL` (e.g. `http://stt-adapter:8092`) and WS path what SDK expects (`ws(s)://host/v1/listen`). Sample rate **16 kHz mono** (hardcoded `omiListen.ts:77,87`). Adapter may ignore `diarize/model` params — backend tolerates single-speaker `SPEAKER_0` (spec: “No diarizer → single-stream”).

---

### 3c. Updater 404 tolerance + required flag if it hard-errors

**Verdict: 404 is tolerated as “no update” — no hard error, no flag required. Updater disabled in dev (`!app.isPackaged`).**

Evidence:

- `desktop/windows/src/main/windowsUpdateFeed.ts:50-65` — resolver throws on `!response.ok` (includes 404): `if (!response.ok) throw new Error(\`Windows update feed resolution failed (${response.status})\`)`.
- `desktop/windows/src/main/updater.ts:155-162` — feed selector creation (only when not `OMI_UPDATER_DEV`).
- `updater.ts:188-197` — periodic check is **non-fatal**:
  ```typescript
  const check = async (): Promise<void> => {
    try { await runPreparedUpdateCheck(); }
    catch (e) { console.warn('[updater] check failed (non-fatal):', e.message); }
  };
  ```
- `updater.ts:109-123` — manual “Check for updates” also non-fatal (returns `{status:'error', message}`).
- `updater.ts:141-145` — updater only starts when packaged on win32 (or `OMI_UPDATER_DEV=1`):
  ```typescript
  if (started || platform !== 'win32') return;
  const devForced = process.env.OMI_UPDATER_DEV === '1';
  if (!app.isPackaged && !devForced) return;
  ```

**Behavior with 404 from `VITE_OMI_API_BASE`:** `resolveWindowsUpdateFeedUrl` throws `Windows update feed resolution failed (404)`, `runPreparedUpdateCheck` rejects, `check()` logs `warn` and returns, no `pendingUpdate` staged, next check in 4h (`CHECK_INTERVAL_MS=4*60*60*1000`, `updater.ts:26`). No crash loop, no dialog.

**Flag to disable if hard-error were needed:** Leave feed 404ing (already tolerated), or set `OMI_UPDATER_DEV` not set and run unpackaged, or patch `updater.ts:143` to early-return when `VITE_OMI_API_BASE` is self-host placeholder. **Self-host does not need a flag — 404 tolerance is sufficient.** To silence `warn`, make `GET /v2/desktop/update-feed/windows` return `200 {feed_url: "https://github.com/BasedHardware/omi/releases/download/vX-windows/"}` or keep 404.

---

### 3d. Blank `VITE_POSTHOG_KEY` behavior

**Finding: blank `VITE_POSTHOG_KEY` does NOT disable analytics — it falls back to hardcoded default key and keeps posting to `https://us.i.posthog.com`. To truly disable, patch `analytics.ts`.**

Evidence:

- `desktop/windows/src/renderer/src/lib/analytics.ts:9-11`
  ```typescript
  const POSTHOG_KEY =
    (import.meta.env.VITE_POSTHOG_KEY as string) || 'phc_z3qUFhGUgYIOMYnfxVSrLmYISQvbgph8iREQv3sez3Y';
  ```
- `analytics.ts:13-31` — `trackEvent` always does `fetch('https://us.i.posthog.com/i/v0/e/', {method:'POST', body: {api_key: POSTHOG_KEY, ...}})`. No early-return when blank.
- `analytics.ts:9` — `POSTHOG_HOST = 'https://us.i.posthog.com'` hardcoded (comment: “intentionally fixed to CSP”).

**What must change to blank-disable (required for self-host “analytics off”):**

In `analytics.ts:10-11`, guard:
```typescript
const POSTHOG_KEY = import.meta.env.VITE_POSTHOG_KEY as string | undefined;
export function trackEvent(...) {
  if (!POSTHOG_KEY) return; // blank → disabled
  ...
}
```
Then set `VITE_POSTHOG_KEY=` (empty) in self-host `.env` and rebuild (`pnpm run dev`). Alternatively set `VITE_POSTHOG_KEY=disabled` with check `if (!POSTHOG_KEY || POSTHOG_KEY === 'disabled') return;`. Until patched, blank still sends under `phc_z3qUF...`.

---

### 3e. `ADMIN_KEY<uid>` dev-auth bypass — header/param, exact format

**Mechanism:** `Authorization: Bearer <ADMIN_KEY><uid>` — raw token is `ADMIN_KEY` env value concatenated with Firebase `uid`, no separator.

Evidence:

- `backend/utils/other/endpoints.py:91-123` (`verify_token`):
  ```python
  admin_key = os.getenv('ADMIN_KEY')
  if admin_key and os.getenv('ADMIN_KEY_AUTH_ENABLED', 'true').lower() == 'true':
      if len(admin_key) < 16:
          logger.warning('ADMIN_KEY is under 16 chars — trivially guessable...')
      candidate = token[: len(admin_key)].encode()
      if hmac.compare_digest(candidate, admin_key.encode()) and len(token) > len(admin_key):
          impersonated_uid = token[len(admin_key) :]
          logger.warning('ADMIN_KEY auth used to impersonate uid=%s', impersonated_uid)
          return impersonated_uid
  ```
- Header: `get_current_user_uid:165-186` extracts `authorization.split(' ')[1]` — so header is `Authorization: Bearer <token>` where `<token> = ADMIN_KEY + uid`.
- Env: `backend/.env.template:39-42`:
  ```
  ADMIN_KEY=
  ADMIN_KEY_AUTH_ENABLED=true
  ```
- WS variants: `endpoints.py:284-308` (`_verify_ws_auth`), `401-435` also call `verify_token`, so **WS** `Authorization: Bearer <ADMIN_KEY><uid>` and first-message `{"type":"auth","token":"<ADMIN_KEY><uid>"}` both work.

**Exact self-host curl (Task 4):**

```bash
ADMIN_KEY=$(openssl rand -hex 16)  # ≥16 chars, put in /opt/omi/.env
UID="test-selfhost-uid-001"
curl -s "https://omi-api.xuanloi.me/v1/health" \
  -H "Authorization: Bearer ${ADMIN_KEY}${UID}" | jq .
curl -s "https://omi-api.xuanloi.me/v1/users/me" \
  -H "Authorization: Bearer ${ADMIN_KEY}${UID}" -H "X-App-Platform: windows" | jq .
```

To disable: `ADMIN_KEY_AUTH_ENABLED=false` (or unset `ADMIN_KEY`). Default `true` so existing CI keeps working (`endpoints.py:114` comment). Auditable: every use logs `WARNING ADMIN_KEY auth used to impersonate uid=...` (`endpoints.py:122`). Timing-safe: `hmac.compare_digest`.

---

### 3f. Health routes (controller-verified facts)

| Service | Route | File:line | Response |
|---------|-------|-----------|----------|
| Python backend (`backend/main.py`) | `GET /v1/health` (also `HEAD`) | `backend/routers/other.py:8` `@router.api_route("/v1/health", methods=["GET","HEAD"])` | `{"status":"ok"}` |
| Desktop backend (`backend/desktop_backend.py`) | `GET /health` and `GET /` (alias) | `backend/routers/desktop_core.py:77-78` | `{"status":"healthy","service":"omi-desktop-backend","version":"0.1.0","chat_contract_version":"1", ...}` |
| Desktop backend readiness | `GET /ready` | `backend/routers/desktop_core.py:82-92` | `200 {"status":"ready",...}` or `503` with `failure_class` |
| Pusher (`pusher/main.py`) | `GET /health` | `backend/pusher/main.py:66-68` | `{"status":"healthy"}` |
| Pusher readiness / drain | `GET /ready`, `POST /__internal/drain` (loopback-only) | `pusher/main.py:71-92` | LB readiness gate |

Dockerfile paths (controller-verified): `backend/Dockerfile` (main, `uvicorn main:app`), `backend/Dockerfile.desktop_backend` (`uvicorn desktop_backend:create_app --factory`), `backend/pusher/Dockerfile` (`uvicorn pusher.main:app`).

---

## 4. Degradation checklist — each spec claim mapped to a table row

| Spec degradation claim | Table row(s) | Evidence: what degrades, what stays up |
|------------------------|--------------|----------------------------------------|
| **No diarizer → single-stream transcripts** | §1 D26/D27 `wss://…/v4/listen` (`diarize=True` `streaming.py:850` but adapter returns `SPEAKER_0` only) + §1 D11 `from-segments` `speaker: SPEAKER_X` synthesized | Without GPU diarizer, `word.speaker` is `0` for all words, coalesces to one `SPEAKER_0` (`streaming.py:681` branch never taken). UI single-stream; no 500. Pusher stays up. |
| **No NLLB → translation UI off** | Internal `HOSTED_TRANSLATION_API_URL` / `nllb_translation/` (not Windows-app endpoint) | `utils/translation.py` checks `HOSTED_TRANSLATION_API_URL` before calling; when blank returns original text. Windows shows “Translate” disabled; no API error. |
| **No Typesense/Pinecone → search falls back to basic** | §1 row 25: `GET /v3/memories` still works; semantic `POST /v3/memories/search` 500s internally but `database/vector_db.py` fails open | With `TYPESENSE_HOST`, `PINECONE_API_KEY` blank, vector DB returns `[]`; app shows “Search (basic)”. No block on listen/chat. |
| **No Stripe → Plan/Usage degraded** | §1 row 25: `GET /v1/users/me/subscription`, `/v1/users/me/usage-quota`, `POST /v1/payments/*` (`lib/billing.ts:27,35,39,43,533-546`) | `STRIPE_API_KEY=` blank → `routers/payment.py` returns `503` “Stripe not configured” (dev skips price validation). `billing.ts` catches and shows “Usage limit UI without billing — acceptable”. |
| **STT failure → retries/fails with clear error; pusher stays up** | §1 rows 26/27 (WS), `streaming.py` circuit breakers, `connect_stt_socket_with_fallback` (`streaming.py:143-242`) | STT WS `error`/`close` → `liveMicSession` retries per `calculate_backoff_with_jitter`, then `from-segments` rescue. Pusher `/health` stays 200. |
| **App update checker 404 → “no update”** | §1 row 20 + §3c | `windowsUpdateFeed.ts:61` throws on 404, `updater.ts:192-195` logs non-fatal `warn`, no `pendingUpdate`, next check 4h. Tolerated; no flag needed. |
| **No GPU sub-services (parakeet, vad, nllb) — backend degrades** | `AGENTS.md` Service Map + `streaming.py:143-242` fallback chain | `STT_SERVICE_MODELS` ordering (`config/stt_provider_policy.py:133-142` `STREAMING ('dg-nova-3','modulate-velma-2','parakeet')`) — if `HOSTED_PARAKEET_API_URL` unset and `MODULATE_API_KEY` blank, only Deepgram self-hosted serves. Backend starts; tests in `tests/integration` not CI. |
| **Notifications, memory-maintenance cron, sync-backfill, integrations — not needed, app tolerates missing endpoints** | §1 row 25 sprawl (`/v1/sync/*`, `/v1/mcp/*`, `/v1/integrations/*`, `modal/*`) | Windows never calls these on core path; when called they 404/503 and UI shows degraded (e.g. “Sync past recordings” paced `BACKFILL_HOURLY_CAP=25`). Core `listen+chat+memory` unaffected. |

All 6 + 2 spec claims have a row — no orphan “degradation” promise without concrete endpoint or flag.

---

## 5. Open questions — things the audit could not resolve, with file:line needing closer look

| # | Question | File:line needing closer look | Impact | Proposed next step for Task 4 |
|---|----------|-------------------------------|--------|-------------------------------|
| Q1 | **Desktop backend `ANTHROPIC_API_KEY` vs 9Router for managed chat** — 9Router is OpenAI-compatible. Desktop backend managed chat (`routers/desktop_chat.py:26,239`) uses `anthropic_client` or `GatewayContextChatOpenAI`, not plain `ChatOpenAI` vs 9Router. Can 9Router serve Anthropic `messages.create` shape? | `backend/routers/desktop_chat.py:26-31`, `:1063-1095`, `desktop_backend.py` | If 9Router is OpenAI-only, desktop backend 401. Must set `ANTHROPIC_API_KEY=9router-key` + proxy or `OMI_LLM_GATEWAY_URL=https://9router.xuanloi.me/v1` with `OMI_LLM_GATEWAY_FEATURE_MODE=gateway`. | Test `curl https://9router.xuanloi.me/v1/chat/completions` vs `POST /v1/messages` with 9Router key. |
| Q2 | **Deepgram BYOK header interaction with self-hosted** — `streaming.py:784-801` returns `managed` when `is_dg_self_hosted` without checking `get_byok_key('deepgram')`, but Windows `omiListen.ts:31-39` always sends `X-BYOK-*` when 4 keys present. Will self-hosted 403 BYOK-enrolled user? | `backend/utils/stt/streaming.py:784-801`, `backend/utils/byok.py`, `desktop/windows/src/main/ipc/omiListen.ts:31-39` | Enrolled user with 4 keys gets 403 on listen. Workaround: not call `byok-active` or clear keys. | Task 6: test BYOK-enrolled `ADMIN_KEY<uid>` + `X-BYOK-*` handshake vs self-hosted. |
| Q3 | **`DEEPGRAM_SELF_HOSTED_URL` scheme — WS vs HTTP** — SDK `DeepgramClientOptions(url=endpoint)` (`streaming.py:591`) used for both WS and HTTP. Need `ws://` or `http://`? | `backend/utils/stt/streaming.py:585-592`, `:614-618` | Wrong scheme → `WebSocketException` and 100% STT failure. | Task 6: test `http://stt-adapter:8092` vs `https://omi-stt.xuanloi.me` with SDK. |
| Q4 | **Sherpa `vi` + `multi` coverage** — Windows sends `language` as `en`/`vi`/`multi`. `config/stt_provider_policy.py:95-96` has `vi` in modulate but Deepgram list (`streaming.py:281-367`) also `vi`. Will adapter advertising `vi` only handle `multi`? | `backend/config/stt_provider_policy.py:95-96`, `backend/utils/stt/streaming.py:281-367` | If adapter only `vi` but app sends `multi`, `get_stt_service_for_language('multi')` may skip self-hosted and try Modulate → unavailable. | Task 6: make adapter respond to `language=multi` as `vi` and test both. |
| Q5 | **Updater `feed_url` trust allowlist** — `main/windowsUpdateFeed.ts:37-46` only allows `https://github.com` + `^/BasedHardware/omi/releases/download/v\d+\.\d+...-windows/$`. Self-host artifacts on own domain rejected as `untrusted feed_url`. | `desktop/windows/src/main/windowsUpdateFeed.ts:37-48` | Cannot self-host update artifacts on own domain without patch. Workaround: keep GitHub origin (spec says 404 → “no update”). | Documented limitation; Task 7 leaves GitHub origin. |
| Q6 | **PostHog blank-disable requires rebuild** — `analytics.ts:9-11` hardcodes fallback at build time (`import.meta.env` Vite-inlined). Changing `VITE_POSTHOG_KEY=` after build has no effect. | `desktop/windows/src/renderer/src/lib/analytics.ts:9-11`, Vite build | Operator who sets `VITE_POSTHOG_KEY=` in `/opt/omi/.env` but doesn’t rebuild installer still ships old key. | Task 7 must note: `VITE_POSTHOG_KEY=` change requires `pnpm run build` + new installer. |

_No blocking open question for core `listen+chat+memory`; Q1–Q4 are STT/desktop-chat wiring refinements, Q5–Q6 are operational notes._

---

## Appendix — Verified paths and commands

- Dockerfiles: `backend/Dockerfile` (main), `backend/Dockerfile.desktop_backend`, `backend/pusher/Dockerfile` — verified `EXPOSE 8080`, `uvicorn` entrypoints.
- Health curls (after `docker compose up` on VPS):
  ```bash
  curl -s https://omi-api.xuanloi.me/v1/health | jq .          # → {"status":"ok"}
  curl -s https://omi-desk.xuanloi.me/health | jq .            # → {"status":"healthy",...}
  curl -s https://omi-desk.xuanloi.me/ready | jq .             # → {"status":"ready"} (needs REDIS_DB_HOST)
  curl -s https://omi-ws.xuanloi.me/health | jq .              # → {"status":"healthy"} (pusher)
  ```
- Authed curl (Task 4):
  ```bash
  ADMIN_KEY=...  # from /opt/omi/.env
  UID=$(openssl rand -hex 8)
  curl -s https://omi-api.xuanloi.me/v1/users/me \
    -H "Authorization: Bearer ${ADMIN_KEY}${UID}" -H "X-App-Platform: windows" | jq .
  ```
- STT adapter probe (Task 6):
  ```bash
  curl -s http://stt-adapter:8092/v1/health || echo "adapter must expose Deepgram-compatible health at DEEPGRAM_SELF_HOSTED_URL"
  ```

---

*Generated by Task 1 audit — read-only. Cite this doc as the source for Tasks 2-9. Re-run `grep -R 'omiApi\.|desktopApi\.|VITE_OMI' desktop/windows/src` to diff future app changes.*


