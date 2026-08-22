"""omi-stt-adapter — FastAPI WebSocket speaking the pinned Deepgram self-hosted subset.

Serves /v1/stream (brief) and /v1/listen (the path deepgram-sdk 4.8.1 derives from
DEEPGRAM_SELF_HOSTED_URL; see task-1-report.md line 66) with the same handler.
No auth: reachable only on the internal Docker network (compose binds 127.0.0.1).
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

import protocol
import recognizer as recognizer_mod

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("stt_adapter")

MAX_FRAME_BYTES = int(os.getenv("STT_MAX_FRAME_BYTES", str(16000 * protocol.BYTES_PER_SAMPLE * 10)))

_recognizer_factory = None


def set_recognizer_factory(factory) -> None:
    """Install a recognizer factory override (used by the test suite)."""
    global _recognizer_factory
    _recognizer_factory = factory


def create_recognizer():
    if _recognizer_factory is not None:
        return _recognizer_factory()
    model_dir = recognizer_mod.load_model(os.getenv("STT_MODEL_SOURCE", recognizer_mod.DEFAULT_MODEL_URL))
    num_threads = int(os.getenv("STT_NUM_THREADS", "2"))
    return recognizer_mod.ViRecognizer(model_dir=model_dir, num_threads=num_threads)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the shared engine at boot so the first WS connection never pays the
    # model download/ONNX-session cost. A failed download exits the container;
    # compose restarts until healthy rather than serving a dead endpoint.
    if _recognizer_factory is not None:
        logger.info("recognizer factory overridden; skipping model preload")
    else:
        await async_to_thread(create_recognizer)
    yield


async def async_to_thread(fn):
    import asyncio

    return await asyncio.to_thread(fn)


app = FastAPI(title="omi-stt-adapter", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": recognizer_mod.MODEL_DIR_NAME,
        "sample_rate": protocol.SAMPLE_RATE,
        "encoding": protocol.ENCODING,
        "engine_loaded": bool(recognizer_mod._ENGINES),
    }


async def _reject(ws: WebSocket, message: str, close_code: int = 1008) -> None:
    await ws.send_text(protocol.encode_error(message, close_code))
    await ws.close(code=close_code)


async def _stream_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    rec = None
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            text, data = msg.get("text"), msg.get("bytes")

            if data is not None:
                if rec is None:
                    await _reject(ws, "audio frame received before Start")
                    return
                if len(data) % protocol.BYTES_PER_SAMPLE != 0 or len(data) > MAX_FRAME_BYTES:
                    await _reject(ws, f"invalid PCM16 frame of {len(data)} bytes")
                    return
                # ONNX decode is CPU-bound: keep it off the event loop so
                # KeepAlive/receive() stay responsive during long utterances.
                for segment in await async_to_thread(lambda: rec.transcribe_chunk(data)):
                    await ws.send_text(
                        protocol.encode_results(
                            segment["text"],
                            start_seconds=float(segment.get("start", 0.0)),
                            duration_seconds=float(segment.get("duration", 0.0)),
                            is_final=bool(segment.get("is_final", True)),
                        )
                    )
                continue

            if text is None:
                continue
            try:
                event = protocol.parse_client_message(text)
            except protocol.ProtocolError as err:
                await _reject(ws, err.message)
                return
            etype, payload = event["type"], event["payload"]

            if etype == "Start":
                if rec is not None:
                    await _reject(ws, "connection already started")
                    return
                try:
                    protocol.validate_start(payload)
                except protocol.ProtocolError as err:
                    await _reject(ws, err.message, err.close_code)
                    return
                rec = create_recognizer()
                logger.info(
                    "session started language=%s interim=%s",
                    payload.get("language", "vi"),
                    payload.get("interim_results", False),
                )
                await ws.send_text(
                    protocol.encode_metadata(str(uuid.uuid4()), recognizer_mod.MODEL_DIR_NAME)
                )
            elif etype == "KeepAlive":
                continue
            elif etype in ("Finalize", "CloseStream"):
                if rec is not None:
                    for segment in await async_to_thread(rec.flush):
                        await ws.send_text(
                            protocol.encode_results(
                                segment["text"],
                                start_seconds=float(segment.get("start", 0.0)),
                                duration_seconds=float(segment.get("duration", 0.0)),
                                is_final=bool(segment.get("is_final", True)),
                                from_finalize=(etype == "Finalize"),
                            )
                        )
                if etype == "CloseStream":
                    await ws.close(code=1000)
                    return
            else:
                logger.warning("ignoring unknown message type %r", etype)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


app.add_api_websocket_route("/v1/stream", _stream_endpoint)
app.add_api_websocket_route("/v1/listen", _stream_endpoint)
