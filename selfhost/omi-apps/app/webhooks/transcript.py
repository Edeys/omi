import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import settings

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


async def _run_analysis_job(uid: str, session_id: str) -> None:
    from app.llm.client import llm_client
    from app.notifications.sender import notification_sender
    from app.processing.prompts import make_llm_chat
    from app.processing.transcript_analyzer import run_analysis

    text = await run_analysis(uid, session_id, make_llm_chat(llm_client))
    if not text:
        return
    logger.info("insight ready uid=%s session=%s len=%d", uid, session_id, len(text))
    if settings.notify_on_insight:
        sent = await notification_sender.send(uid, "Omi Insight", text)
        if sent:
            logger.info("insight notification delivered uid=%s session=%s", uid, session_id)


@router.post("/webhook/transcript")
async def transcript_webhook(request: Request, background: BackgroundTasks) -> dict[str, Any]:
    uid = request.query_params.get("uid")
    session_id = request.query_params.get("session_id") or "default"
    if not uid:
        raise HTTPException(status_code=422, detail="uid query parameter is required")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    from app.processing.transcript_analyzer import record_for_analysis
    from app.store.sessions import store

    segments = parse_segments(body)
    fresh = await store.append_segments(uid, session_id, segments)
    buffered = await store.get_segments(uid, session_id)

    scheduled = False
    if await record_for_analysis(
        uid, session_id, settings.analysis_min_new_words, settings.analysis_interval_seconds
    ):
        background.add_task(_run_analysis_job, uid, session_id)
        scheduled = True

    logger.info(
        "transcript uid=%s session=%s received=%d new=%d buffered=%d analysis=%s",
        uid,
        session_id,
        len(segments),
        len(fresh),
        len(buffered),
        "scheduled" if scheduled else "skipped",
    )
    return {
        "status": "ok",
        "received": len(segments),
        "new": len(fresh),
        "buffered": len(buffered),
        "analysis_scheduled": scheduled,
    }


@router.get("/webhook/transcript/insight")
async def transcript_insight(request: Request) -> dict[str, Any]:
    uid = request.query_params.get("uid")
    session_id = request.query_params.get("session_id") or "default"
    if not uid:
        raise HTTPException(status_code=422, detail="uid query parameter is required")
    from app.processing.transcript_analyzer import insight_store

    insight = await insight_store.get(uid, session_id)
    if not insight:
        return {"status": "empty"}
    return {"status": "ok", "insight": insight.get("text"), "analyzed_segments": insight.get("analyzed_segments")}
