import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import settings

logger = logging.getLogger("omi-apps.webhooks.memory")

router = APIRouter()


def parse_memory_payload(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="memory payload must be a JSON object")
    if not body.get("id") and not body.get("created_at"):
        raise HTTPException(status_code=422, detail="memory payload requires id or created_at")
    return body


def get_memory_store():
    from app.store.memory_store import MemoryStore

    return MemoryStore(settings.memory_store_dir)


async def _process_memory_job(uid: str, memory: dict[str, Any]) -> None:
    from app.llm.client import llm_client
    from app.processing.prompts import make_llm_chat
    from app.processing.memory_extractor import extract_from_memory

    store = get_memory_store()

    async def chat(messages):
        return await llm_client.chat(messages, max_tokens=1200, temperature=0.1, timeout_seconds=180)

    try:
        result = await extract_from_memory(
            uid,
            memory,
            chat,
            store,
            forward_url=settings.forward_url or None,
        )
    except Exception as exc:
        logger.error("memory processing failed uid=%s id=%s err=%s", uid, memory.get("id"), type(exc).__name__)
        return
    total = result.get("action_items", 0) + result.get("notes", 0) + result.get("decisions", 0)
    logger.info("memory processed uid=%s id=%s extracted=%d", uid, memory.get("id"), total)


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
    background.add_task(_process_memory_job, uid, memory)
    return {"status": "ok"}


@router.get("/webhook/memory/items")
async def list_items(request: Request) -> dict[str, Any]:
    uid = request.query_params.get("uid")
    kind = request.query_params.get("kind")
    limit_raw = request.query_params.get("limit") or "100"
    try:
        limit = max(1, min(int(limit_raw), 500))
    except ValueError:
        raise HTTPException(status_code=422, detail="limit must be an integer")
    if not uid:
        raise HTTPException(status_code=422, detail="uid query parameter is required")
    items = get_memory_store().list_items(uid, kind=kind, limit=limit)
    return {"status": "ok", "count": len(items), "items": items}
