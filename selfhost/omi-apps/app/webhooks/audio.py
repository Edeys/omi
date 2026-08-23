import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("omi-apps.webhooks.audio")

router = APIRouter()


@router.post("/webhook/audio")
async def audio_webhook(request: Request) -> dict[str, Any]:
    uid = request.query_params.get("uid")
    sample_rate = request.query_params.get("sample_rate")
    if not uid:
        raise HTTPException(status_code=422, detail="uid query parameter is required")
    try:
        sample_rate_int = int(sample_rate) if sample_rate else 16000
    except ValueError:
        raise HTTPException(status_code=422, detail="sample_rate must be an integer")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty audio body")
    duration_seconds = len(body) / 2 / max(sample_rate_int, 1)
    logger.info(
        "audio chunk uid=%s bytes=%d sample_rate=%d approx_seconds=%.2f (pipeline lands in Phase 5)",
        uid,
        len(body),
        sample_rate_int,
        duration_seconds,
    )
    return {"status": "ok", "bytes": len(body), "sample_rate": sample_rate_int}
