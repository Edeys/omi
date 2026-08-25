"""LLM punctuation cho transcript tiếng Việt lúc finalization.

Env OMI_PUNCTUATE_ENABLED=true để bật. Fail-open: mọi lỗi LLM trả nguyên
segments gốc — punctuation là enhancement, không được phá pipeline.
Prompt yêu cầu LLM trả về CÙNG SỐ dòng, mỗi dòng = 1 segment đã có dấu.
"""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)

_PROMPT = (
    'Bạn là bộ chèn dấu câu cho bản ghi hội thoại tiếng Việt. '
    'Dưới đây là {n} dòng, mỗi dòng là 1 đoạn hội thoại. '
    'Hãy viết lại CHÍNH XÁC từng dòng, chỉ THÊM dấu câu (.,?!...) và viết hoa '
    'chữ cái đầu nếu cần. KHÔNG đổi từ, KHÔNG thêm/xóa/dịch nội dung, '
    'KHÔNG thêm giải thích. Trả về đúng {n} dòng, mỗi dòng 1 đoạn.\n\n'
)


def _get_llm():
    from utils.llm.providers import get_or_create_openai_compatible_llm

    model = os.getenv('OMI_LIGHT_MODEL', 'mimo-v2.5')
    return get_or_create_openai_compatible_llm('openai', model)


def punctuate_segments(uid: str, segments: List) -> List:
    if os.getenv('OMI_PUNCTUATE_ENABLED', '').strip().lower() != 'true':
        return segments
    texts = [s.text for s in segments]
    if not any(t.strip() for t in texts):
        return segments
    prompt = _PROMPT.format(n=len(texts)) + '\n'.join(texts)
    try:
        llm = _get_llm()
        response = llm.invoke(prompt)
        content = getattr(response, 'content', response)
        lines = [ln for ln in str(content).splitlines() if ln.strip()]
        if len(lines) != len(texts):
            logger.warning('punctuate: line count mismatch %d != %d, skip', len(lines), len(texts))
            return segments
        out = []
        for seg, new_text in zip(segments, lines):
            out.append(seg.model_copy(update={'text': new_text}))
        logger.info('punctuate: updated %d segments uid=%s', len(out), uid)
        return out
    except Exception as e:
        logger.warning('punctuate failed uid=%s: %s', uid, e)
        return segments
