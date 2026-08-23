import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

logger = logging.getLogger("omi-apps.webhooks.day_summary")

router = APIRouter()


def parse_summary_payload(body: Any) -> tuple[dict[str, Any], str | None]:
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="day summary payload must be a JSON object")
    summary_json = body.get("summary_json")
    legacy_summary = body.get("summary")
    if summary_json is None and legacy_summary is None:
        raise HTTPException(status_code=422, detail="payload requires summary_json (or legacy summary)")
    if summary_json is not None and not isinstance(summary_json, dict):
        raise HTTPException(status_code=422, detail="summary_json must be a JSON object")
    return summary_json or {}, legacy_summary


async def process_day_summary(uid: str, summary_json: dict[str, Any], created_at: Any) -> None:
    headline = summary_json.get("headline") if isinstance(summary_json.get("headline"), str) else ""
    logger.info(
        "day summary queued uid=%s headline_len=%d created_at=%s (persistence lands in Phase 7)",
        uid,
        len(headline),
        created_at,
    )


@router.post("/webhook/day_summary")
async def day_summary_webhook(request: Request, background: BackgroundTasks) -> dict[str, Any]:
    uid = request.query_params.get("uid")
    if not uid:
        raise HTTPException(status_code=422, detail="uid query parameter is required")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    summary_json, _legacy = parse_summary_payload(body)
    background.add_task(process_day_summary, uid, summary_json, body.get("created_at"))
    return {"status": "ok"}
