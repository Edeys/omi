import json
import logging
from typing import Any

logger = logging.getLogger("omi-apps.stt")

START_MESSAGE = {
    "type": "Start",
    "sample_rate": 16000,
    "encoding": "linear16",
    "channels": 1,
    "interim_results": False,
    "language": "vi",
}


async def transcribe_pcm(
    pcm: bytes,
    connect: Any,
    sample_rate: int = 16000,
    frame_bytes: int = 3200,
) -> str:
    """Stream PCM16 through the stt-adapter WS and return concatenated finals.

    connect is an async callable returning a connected websocket exposing
    send/send_text/recv — injectable for tests.
    """
    ws = await connect()
    transcripts: list[str] = []
    start = dict(START_MESSAGE)
    start["sample_rate"] = int(sample_rate)
    try:
        await ws.send(json.dumps(start))
        offset = 0
        while offset < len(pcm):
            await ws.send(pcm[offset : offset + frame_bytes])
            offset += frame_bytes
        await ws.send(json.dumps({"type": "Finalize"}))
        while True:
            raw = await ws.recv()
            if isinstance(raw, bytes):
                continue
            doc = json.loads(raw)
            mtype = doc.get("type")
            if mtype == "Metadata":
                continue
            if mtype == "Error":
                logger.warning("stt-adapter error frame: %s", str(doc)[:120])
                break
            if mtype == "Results":
                alt = (
                    doc.get("channel", {})
                    .get("alternatives", [{}])[0]
                )
                text = (alt.get("transcript") or "").strip()
                if doc.get("is_final") and text:
                    transcripts.append(text)
                if doc.get("from_finalize"):
                    break
            if mtype is None:
                continue
    except Exception as exc:
        logger.warning("stt streaming ended early (%s), keeping partial transcript", type(exc).__name__)
    finally:
        try:
            await ws.send(json.dumps({"type": "CloseStream"}))
        except Exception:
            pass
    return " ".join(transcripts).strip()
