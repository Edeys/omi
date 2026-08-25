import argparse
import asyncio
import json
import logging
import os
import struct
import time
from dataclasses import dataclass
from typing import Optional
import urllib.request
import urllib.error

import websockets

logger = logging.getLogger("soak_real_auth")
logging.basicConfig(level=logging.INFO)


@dataclass
class SoakConfig:
    users: int = 5
    duration: int = 600
    ramp_seconds: int = 60
    silence_interval: float = 5.0


def mint_custom_token(uid: str) -> bytes:
    import firebase_admin
    from firebase_admin import auth as admin_auth

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
    return admin_auth.create_custom_token(uid)


def exchange_custom_token_for_id_token(custom_token: bytes, api_key: str) -> Optional[str]:
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={api_key}"
    data = json.dumps({
        "token": custom_token.decode("utf-8"),
        "returnSecureToken": True
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            resp_data = json.loads(response.read().decode())
            return resp_data.get("idToken")
    except urllib.error.URLError as e:
        logger.error("Failed to exchange custom token: %s", e)
        return None


async def run_one_user(uid: str, duration: int, silence_interval: float, api_key: str, ws_url: str):
    logger.info("User %s starting", uid)
    try:
        custom_token = await asyncio.to_thread(mint_custom_token, uid)
        id_token = await asyncio.to_thread(exchange_custom_token_for_id_token, custom_token, api_key)
        
        if not id_token:
            logger.error("User %s failed to get id_token", uid)
            return

        headers = {"Authorization": f"Bearer {id_token}"}
        
        async with websockets.connect(f"{ws_url}?language=vi&sample_rate=16000&encoding=linear16", extra_headers=headers) as ws:
            logger.info("User %s connected to WS", uid)
            start_time = time.time()
            
            # 600ms of silence at 16000Hz, 16-bit (2 bytes per sample) -> 9600 samples -> 19200 bytes
            silence_frame = b'\x00' * 19200
            
            while time.time() - start_time < duration:
                await ws.send(silence_frame)
                await asyncio.sleep(silence_interval)
                
            logger.info("User %s completed", uid)
            
    except Exception as e:
        logger.error("User %s error: %s", uid, e)


async def main(cfg: SoakConfig):
    api_key = os.getenv("FIREBASE_API_KEY")
    ws_url = os.getenv("HOSTED_PUSHER_API_URL", "ws://127.0.0.1:8000/v4/listen")
    ws_url = ws_url.replace("http://", "ws://").replace("https://", "wss://")
    
    if not api_key:
        logger.warning("FIREBASE_API_KEY not set. Soak test might fail to exchange tokens.")
    
    uids = [f"soak-{i}" for i in range(cfg.users)]
    tasks = []
    
    for i, uid in enumerate(uids):
        delay = (cfg.ramp_seconds / max(1, cfg.users - 1)) * i if cfg.users > 1 else 0
        
        async def delayed_run(uid_param=uid, delay_param=delay):
            await asyncio.sleep(delay_param)
            await run_one_user(uid_param, cfg.duration, cfg.silence_interval, api_key, ws_url)
            
        tasks.append(asyncio.create_task(delayed_run()))
        
    await asyncio.gather(*tasks)
    
    logger.info("Soak test completed. To check stale recoveries:")
    logger.info("docker compose logs backend --since 10m | grep -c 'recovering stale'")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--users", type=int, default=5)
    p.add_argument("--duration", type=int, default=600)
    p.add_argument("--ramp", type=int, default=60)
    args = p.parse_args()
    asyncio.run(main(SoakConfig(users=args.users, duration=args.duration, ramp_seconds=args.ramp)))
