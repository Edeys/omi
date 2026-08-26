"""Verify STT routing: stream real voice through production /v4/listen (inside backend container).

Streams /tmp/sample_u8.pcm (8-bit unsigned PCM16k mono) as codec=pcm8,
collects transcript messages, prints them + which engine served (from logs side).
"""
import asyncio
import json
import os
import sys
import time
import urllib.request

import websockets

try:  # new asyncio implementation (websockets >= 12)
    from websockets.asyncio.client import connect as ws_connect
    HEADERS_KW = 'additional_headers'
except ImportError:  # legacy client
    from websockets.legacy.client import connect as ws_connect
    HEADERS_KW = 'extra_headers'

WS_URL = 'ws://localhost:8080/v4/listen'
UID = 'soak-test-user-0'
AUDIO = '/tmp/sample_u8.pcm'
SAMPLE_RATE = 16000
CHUNK = 9600          # 0.6s of u8 audio
INTERVAL = 0.55       # slightly faster than realtime
DRAIN_S = 25


def get_id_token() -> str:
    import firebase_admin
    from firebase_admin import credentials, auth

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(os.environ['GOOGLE_APPLICATION_CREDENTIALS']))
    custom = auth.create_custom_token(UID).decode()
    body = json.dumps({'token': custom, 'returnSecureToken': True}).encode()
    req = urllib.request.Request(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={os.environ['FIREBASE_API_KEY']}",
        data=body, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())['idToken']


async def main() -> None:
    token = get_id_token()
    uri = (f"{WS_URL}?uid={UID}&language=vi&sample_rate={SAMPLE_RATE}"
           f"&codec=pcm8&include_speech_profile=false&source=verify")
    headers = {'Authorization': f'Bearer {token}'}
    pcm = open(AUDIO, 'rb').read()
    print(f"audio bytes={len(pcm)} ({len(pcm)/SAMPLE_RATE:.1f}s)", flush=True)

    transcripts: list[str] = []
    raw_messages: list[str] = []

    async def recv_loop(ws):
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed as e:
                print(f'recv closed: {type(e).__name__}: {e}', flush=True)
                return
            except Exception as e:
                print(f'recv ERROR: {type(e).__name__}: {e}', flush=True)
                return
            raw_messages.append(str(msg))
            print(f'<< {str(msg)[:300]}', flush=True)
            try:
                data = json.loads(msg)
            except Exception:
                continue
            if isinstance(data, dict):
                for seg in data.get('segments', []) or []:
                    t = seg.get('text')
                    if t:
                        transcripts.append(t)

    started = time.time()
    async with ws_connect(uri, open_timeout=20, **{HEADERS_KW: headers}) as ws:
        print('connected', flush=True)
        rt = asyncio.create_task(recv_loop(ws))
        sent = 0
        for off in range(0, len(pcm), CHUNK):
            await ws.send(pcm[off:off + CHUNK])
            sent += 1
            await asyncio.sleep(INTERVAL)
        print(f'sent {sent} chunks in {time.time()-started:.1f}s, sending EOS', flush=True)
        try:
            await ws.send('')
        except Exception:
            pass
        end_wait = time.time() + DRAIN_S
        while time.time() < end_wait and not transcripts:
            await asyncio.sleep(0.5)
        await asyncio.sleep(3)
        rt.cancel()

    print('\n=== TRANSCRIPTS ===', flush=True)
    full = ' '.join(transcripts).strip()
    print(full or '(none received)')
    print(f"\n=== total messages received: {len(raw_messages)} ===", flush=True)
    ref = ''
    try:
        ref = open('/tmp/sample.ref.txt', encoding='utf-8').read().strip()
    except Exception:
        pass
    if ref:
        print('\n=== REFERENCE ===')
        print(ref)


if __name__ == '__main__':
    asyncio.run(main())
