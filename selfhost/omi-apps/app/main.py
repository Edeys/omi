import logging
from typing import Any

from fastapi import FastAPI

from app.webhooks import audio, day_summary, memory, transcript

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="omi-apps", version="0.1.0", description="Self-hosted Omi integration apps service")

app.include_router(transcript.router)
app.include_router(audio.router)
app.include_router(memory.router)
app.include_router(day_summary.router)

TOOLS_MANIFEST: dict[str, Any] = {
    "chat_tools": [],
    "chat_messages": {"enabled": False},
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "omi-apps"}


@app.get("/.well-known/omi-tools.json")
def tools_manifest() -> dict[str, Any]:
    return TOOLS_MANIFEST
