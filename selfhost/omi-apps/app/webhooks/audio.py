import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import Response

from app.config import settings

logger = logging.getLogger("omi-apps.webhooks.audio")

router = APIRouter()


def get_audio_store():
    from app.store.audio import AudioStore

    return AudioStore(settings.audio_store_dir)


@router.post("/webhook/audio")
async def audio_webhook(request: Request, background: BackgroundTasks) -> dict[str, Any]:
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

    store = get_audio_store()
    result = store.append_chunk(uid, body, sample_rate_int)
    stale = store.stale_open_files(uid)
    for path in stale:
        background.add_task(_finalize_file, uid, path)
    duration_seconds = len(body) / 2 / max(sample_rate_int, 1)
    logger.info(
        "audio chunk uid=%s bytes=%d sample_rate=%d approx_seconds=%.2f file=%s",
        uid,
        len(body),
        sample_rate_int,
        duration_seconds,
        result["path"].split("/")[-1],
    )
    return {"status": "ok", "bytes": len(body), "sample_rate": sample_rate_int}


async def _finalize_file(uid: str, path: str) -> None:
    store = get_audio_store()
    wav_path = store.finalize(path)
    if wav_path:
        logger.info("audio finalized uid=%s file=%s", uid, wav_path.split("/")[-1])
    if settings.stt_enabled and wav_path:
        from app.webhooks.audio_stt import transcribe_wav_file

        await transcribe_wav_file(uid, wav_path)


@router.get("/webhook/audio/files")
async def list_audio_files(request: Request) -> dict[str, Any]:
    uid = request.query_params.get("uid")
    if not uid:
        raise HTTPException(status_code=422, detail="uid query parameter is required")
    store = get_audio_store()
    return {"status": "ok", "files": store.list_audio(uid)}


@router.get("/webhook/audio/file")
async def download_audio(request: Request) -> Response:
    uid = request.query_params.get("uid")
    name = request.query_params.get("name")
    if not uid or not name:
        raise HTTPException(status_code=422, detail="uid and name query parameters are required")
    store = get_audio_store()
    data = store.read_wav(uid, name)
    if data is None:
        raise HTTPException(status_code=404, detail="file not found")
    return Response(content=data, media_type="audio/wav")
