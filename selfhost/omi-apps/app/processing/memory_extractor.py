import json
import logging
import re
import time
from typing import Any

logger = logging.getLogger("omi-apps.memory-extract")

SYSTEM_PROMPT = (
    "Bạn là bộ trích xuất thông tin từ bản ghi hội thoại tiếng Việt. "
    "Trả về DUY NHẤT một JSON hợp lệ (không markdown, không giải thích) theo dạng: "
    '{"action_items": [{"text": "...", "due_date": "ISO8601 hoặc null"}], '
    '"notes": ["..."], "decisions": ["..."]}. '
    "Chỉ trích xuất những gì thực sự được nói tới. Nếu không có mục nào, trả mảng rỗng."
)

FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def build_extraction_prompt(transcript: str, summary: str) -> list[dict[str, str]]:
    user_content = (
        f"Tóm tắt hội thoại:\n{(summary or '').strip()[:800]}\n\n"
        f"Bản ghi đầy đủ:\n{(transcript or '').strip()[:6000]}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def parse_extraction(text: str) -> dict[str, Any]:
    """Parse LLM output into the extraction shape; tolerant of code fences."""
    if not text:
        raise ValueError("empty extraction")
    candidate = text.strip()
    fenced = FENCE_RE.search(candidate)
    if fenced:
        candidate = fenced.group(1)
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    doc = json.loads(candidate[start : end + 1])
    if not isinstance(doc, dict):
        raise ValueError("extraction is not an object")
    return {
        "action_items": _clean_items(doc.get("action_items")),
        "notes": _clean_strings(doc.get("notes")),
        "decisions": _clean_strings(doc.get("decisions")),
    }


def _clean_strings(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _clean_items(raw: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict) and str(entry.get("text") or "").strip():
                item = {"text": str(entry["text"]).strip(), "due_date": entry.get("due_date")}
            elif isinstance(entry, str) and entry.strip():
                item = {"text": entry.strip(), "due_date": None}
            else:
                continue
            items.append(item)
    return items


async def extract_from_memory(
    uid: str,
    memory: dict[str, Any],
    llm_chat,
    memory_store,
    forward_url: str | None = None,
    http_post=None,
) -> dict[str, Any]:
    """Run LLM extraction over a memory object and persist results.

    Returns counts; failures leave no partial writes.
    """
    transcript = memory.get("transcript") or ""
    summary = memory.get("summary") or ""
    if not transcript and not summary:
        return {"action_items": 0, "notes": 0, "decisions": 0}
    messages = build_extraction_prompt(str(transcript), str(summary))
    raw = await llm_chat(messages)
    try:
        extraction = parse_extraction(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("extraction parse failed uid=%s err=%s raw_len=%d", uid, type(exc).__name__, len(raw))
        fallback = {
            "kind": "raw",
            "text": raw[:2000],
            "created_at": time.time(),
            "memory_id": memory.get("id"),
        }
        memory_store.append(uid, fallback)
        return {"action_items": 0, "notes": 1, "decisions": 0, "fallback": True}

    created_at = time.time()
    memory_id = memory.get("id")
    for item in extraction["action_items"]:
        memory_store.append(
            uid,
            {
                "kind": "action_item",
                "text": item["text"],
                "due_date": item.get("due_date"),
                "created_at": created_at,
                "memory_id": memory_id,
                "done": False,
            },
        )
    for note in extraction["notes"]:
        memory_store.append(uid, {"kind": "note", "text": note, "created_at": created_at, "memory_id": memory_id})
    for decision in extraction["decisions"]:
        memory_store.append(
            uid, {"kind": "decision", "text": decision, "created_at": created_at, "memory_id": memory_id}
        )
    result = {
        "action_items": len(extraction["action_items"]),
        "notes": len(extraction["notes"]),
        "decisions": len(extraction["decisions"]),
    }
    logger.info(
        "extracted uid=%s actions=%d notes=%d decisions=%d",
        uid,
        result["action_items"],
        result["notes"],
        result["decisions"],
    )
    if forward_url:
        try:
            poster = http_post
            if poster is None:
                import httpx

                async def poster(url: str, payload: dict[str, Any]):
                    async with httpx.AsyncClient(timeout=10) as client:
                        return await client.post(url, json=payload)

            await poster(forward_url, {"uid": uid, "extraction": extraction, "memory_id": memory_id})
        except Exception as exc:
            logger.warning("forward failed: %s", type(exc).__name__)
    return result
