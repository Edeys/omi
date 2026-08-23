from typing import Any, Callable

SYSTEM_PROMPT = (
    "Bạn là trợ lý phân tích hội thoại thời gian thực. "
    "Dựa trên các đoạn hội thoại mới nhất, viết MỘT nhận định ngắn gọn (tối đa 2 câu) bằng TIẾNG VIỆT "
    "về chủ đề đang trao đổi và điều đáng lưu ý. Không liệt kê, không markdown, không lặp lại nguyên văn."
)


def build_transcript_insight_prompt(segments: list[dict[str, Any]]) -> list[dict[str, str]]:
    lines = []
    for seg in segments:
        speaker = seg.get("speaker") or "unknown"
        text = (seg.get("text") or "").strip()
        if text:
            lines.append(f"{speaker}: {text}")
    transcript = "\n".join(lines[-40:])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Hội thoại gần đây:\n{transcript}"},
    ]


def make_llm_chat(llm_client: Any) -> Callable:
    async def chat(messages: list[dict[str, str]]) -> str:
        return await llm_client.chat(messages, max_tokens=300, timeout_seconds=120)

    return chat
