import logging
import os

from app.config import settings

logger = logging.getLogger("omi-apps.audio-stt")


async def transcribe_wav_file(uid: str, wav_path: str) -> str | None:
    """Strip the WAV header and forward PCM to stt-adapter; saves .txt next to file."""
    if not wav_path.endswith(".wav"):
        return None
    with open(wav_path, "rb") as fh:
        blob = fh.read()
    pcm = blob[44:]
    if not pcm:
        return None
    from app.stt.forwarder import transcribe_pcm

    async def connect():
        import websockets

        base = settings.stt_ws_url.rstrip("/")
        return await websockets.connect(f"{base}/v1/listen", max_size=None)

    try:
        text = await transcribe_pcm(pcm, connect)
    except Exception as exc:
        logger.warning("stt forward failed uid=%s err=%s", uid, type(exc).__name__)
        return None
    if not text:
        return None
    txt_path = wav_path[:-4] + ".txt"
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    logger.info("stt transcript saved uid=%s file=%s len=%d", uid, os.path.basename(txt_path), len(text))
    return text
