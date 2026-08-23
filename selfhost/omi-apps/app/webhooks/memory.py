import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

logger = logging.getLogger("omi-apps.webhooks.memory")

router = APIRouter()


def parse_memory_payload(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="memory payload must be a JSON object")
    if not body.get("id") and not body.get("created_at"):
        raise HTTPException(status_code=422, detail="memory payload requires id or created_at")
    return body


async def process_memory(uid: str, memory: dict[str, Any]) -> None:
    transcript_len = len(memory.get("transcript") or "")
    summary_len = len(memory.get("summary") or "")
    logger.info(
        "memory queued uid=%s id=%s transcript_len=%d summary_len=%d structured=%s (extraction lands in Phase 6)",
        uid,
        memory.get("id"),
        transcript_len,
        summary_len,
        bool(memory.get("structured")),
    )


@router.post("/webhook/memory")
async def memory_webhook(request: Request, background: BackgroundTasks) -> dict[str, Any]:
    uid = request.query_params.get("uid")
    if not uid:
        raise HTTPException(status_code=422, detail="uid query parameter is required")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    memory = parse_memory_payload(body)
    background.add_task(process_memory, uid, memory)
    return {"status": "ok"}
