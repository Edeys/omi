import logging
import os

logger = logging.getLogger(__name__)

_PROMPT = (
    "Bạn là bộ chèn dấu câu cho bản ghi tiếng Việt. "
    "Viết lại CHÍNH XÁC văn bản sau, chỉ THÊM dấu câu (.,?!...) và viết hoa chữ cái đầu nếu cần. "
    "KHÔNG đổi từ, KHÔNG thêm/xóa/dịch. Chỉ trả về văn bản đã sửa, không giải thích.\n\n"
)

def _get_llm():
    from utils.llm.providers import get_or_create_openai_compatible_llm
    model = os.getenv("OMI_LIGHT_MODEL", "mimo-v2.5")
    return get_or_create_openai_compatible_llm("openai", model)

def punctuate_text_realtime(text: str, language: str = "vi") -> str:
    if not text or not text.strip():
        return text
    if not language.lower().startswith("vi"):
        return text
    if os.getenv("OMI_PUNCTUATE_REALTIME", "").strip().lower() != "true":
        return text
    try:
        llm = _get_llm()
        resp = llm.invoke(_PROMPT + text)
        content = getattr(resp, "content", "") or ""
        candidate = content.strip()
        return candidate if candidate else text
    except Exception as e:
        logger.warning("punctuate_text_realtime failed: %s", e)
        return text
