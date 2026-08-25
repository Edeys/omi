"""Real-auth multi-user soak harness for the Omi self-host.

Runs INSIDE the backend container (has the Firebase SA mounted) or anywhere
with GOOGLE_APPLICATION_CREDENTIALS pointing at the omi-xuan service account.

Flow per virtual user:
  1. firebase_admin.auth.create_custom_token(uid)          (SA already mounted)
  2. exchange custom token -> ID token via identitytoolkit REST
     (needs FIREBASE_API_KEY — the Web API key of project omi-xuan)
  3. wss://omi-ws.xuanloi.me/v4/listen?uid=<uid>&... with
     Authorization: Bearer <idToken>
  4. stream silence PCM16 (16kHz mono) in ~600ms chunks every ~1s for DURATION
     seconds, logging every disconnect/error.

Usage (on the VPS, inside the backend container):
  python /app/soak-real-auth.py --users 3 --duration 300
Env:
  FIREBASE_API_KEY   (required — Web API key from Firebase console)
  OMI_WS_URL         (default wss://omi-ws.xuanloi.me/v4/listen)
"""

import argparse
import asyncio
import json
import os
import struct
import sys
import time

import websockets

SAMPLE_RATE = 16000
CHUNK_SECONDS = 0.6


def create_custom_token(uid: str) -> bytes:
    import firebase_admin.auth as fb_auth

    return fb_auth.create_custom_token(uid)


def exchange_custom_token(custom_token: bytes, api_key: str) -> str:
    import urllib.request

    body = json.dumps({'token': custom_token.decode('utf-8'), 'returnSecureToken': True}).encode()
    req = urllib.request.Request(
        f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data['idToken']


def silence_pcm16(seconds: float) -> bytes:
    n = int(SAMPLE_RATE * seconds)
    return b'\x00\x00' * n


async def user_session(index: int, uid: str, ws_url: str, duration: int, api_key: str, results: dict):
    label = f'[user{index}:{uid[:8]}]'
    try:
        custom_token = await asyncio.to_thread(create_custom_token, uid)
        id_token = await asyncio.to_thread(exchange_custom_token, custom_token, api_key)
    except Exception as e:
        results['errors'] += 1
        print(f'{label} AUTH FAILED: {type(e).__name__}: {e}', flush=True)
        return

    uri = f"{ws_url}?uid={uid}&language=vi&sample_rate={SAMPLE_RATE}&codec=pcm8&include_speech_profile=false&source=soak"
    headers = {'Authorization': f'Bearer {id_token}'}
    chunk = silence_pcm16(CHUNK_SECONDS)

    sent = 0
    try:
        async with websockets.connect(uri, additional_headers=headers, open_timeout=20) as ws:
            results['connected'] += 1
            print(f'{label} connected', flush=True)
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                await ws.send(chunk)
                sent += 1
                # Drain server messages opportunistically so pings/JSON keep flowing.
                try:
                    while True:
                        await asyncio.wait_for(ws.recv(), timeout=0.05)
                except asyncio.TimeoutError:
                    pass
                await asyncio.sleep(1.0 - CHUNK_SECONDS if 1.0 > CHUNK_SECONDS else 0.1)
            # Clean shutdown: server treats empty text frame as EOS.
            try:
                await ws.send('')
            except Exception:
                pass
            results['clean_finish'] += 1
            print(f'{label} done, {sent} chunks sent', flush=True)
    except Exception as e:
        results['disconnects'] += 1
        print(f'{label} DISCONNECT after {sent} chunks: {type(e).__name__}: {e}', flush=True)


async def main_async(users: int, duration: int, ws_url: str, api_key: str, uids: list):
    results = {'connected': 0, 'clean_finish': 0, 'disconnects': 0, 'errors': 0}
    print(f'soak-real-auth: {users} users x {duration}s against {ws_url}', flush=True)
    await asyncio.gather(*(user_session(i, uids[i], ws_url, duration, api_key, results) for i in range(users)))
    print(json.dumps(results), flush=True)
    ok = results['disconnects'] == 0 and results['errors'] == 0 and results['connected'] == users
    print(f"RESULT: {'PASS' if ok else 'FAIL'}", flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--users', type=int, default=int(os.getenv('USERS', '3')))
    parser.add_argument('--duration', type=int, default=int(os.getenv('DURATION', '300')))
    parser.add_argument('--ws-url', default=os.getenv('OMI_WS_URL', 'wss://omi-ws.xuanloi.me/v4/listen'))
    parser.add_argument('--uids', default=os.getenv('SOAK_UIDS', ''), help='Comma-separated real UIDs; default synthetic test-uids')
    args = parser.parse_args()

    api_key = os.getenv('FIREBASE_API_KEY')
    if not api_key:
        print('FIREBASE_API_KEY env required (Web API key of project omi-xuan)', file=sys.stderr)
        sys.exit(2)

    if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(os.environ['GOOGLE_APPLICATION_CREDENTIALS']))

    uid_list = [u.strip() for u in args.uids.split(',') if u.strip()] or [
        f'soak-test-user-{i}' for i in range(args.users)
    ]
    if len(uid_list) < args.users:
        print(f'--uids has {len(uid_list)} entries but --users={args.users}', file=sys.stderr)
        sys.exit(2)

    sys.exit(asyncio.run(main_async(args.users, args.duration, args.ws_url, api_key, uid_list)))
