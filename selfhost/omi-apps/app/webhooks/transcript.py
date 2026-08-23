import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("omi-apps.webhooks.transcript")

router = APIRouter()


def parse_segments(body: Any) -> list[dict[str, Any]]:
    if isinstance(body, dict):
        raw = body.get("segments", body)
    else:
        raw = body
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail="body must contain a segments array")
    segments: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail="each segment must be an object")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        segments.append(
            {
                "speaker": item.get("speaker"),
                "text": text,
                "start": item.get("start"),
                "end": item.get("end"),
            }
        )
    return segments


@router.post("/webhook/transcript")
async def transcript_webhook(request: Request) -> dict[str, Any]:
    uid = request.query_params.get("uid")
    session_id = request.query_params.get("session_id") or "default"
    if not uid:
        raise HTTPException(status_code=422, detail="uid query parameter is required")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    from app.store.sessions import store

    segments = parse_segments(body)
    fresh = await store.append_segments(uid, session_id, segments)
    buffered = await store.get_segments(uid, session_id)
    logger.info(
        "transcript uid=%s session=%s received=%d new=%d buffered=%d",
        uid,
        session_id,
        len(segments),
        len(fresh),
        len(buffered),
    )
    return {"status": "ok", "received": len(segments), "new": len(fresh), "buffered": len(buffered)}
