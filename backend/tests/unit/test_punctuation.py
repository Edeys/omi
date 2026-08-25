"""Punctuation post-processing: ghép các segment text thành 1 khối, gửi LLM
để chèn dấu câu, rồi tách lại theo số segment gốc (1:1 mapping bắt buộc)."""

import sys
import datetime
from unittest.mock import MagicMock, patch


def _seg(text):
    from models.transcript_segment import TranscriptSegment

    now = datetime.datetime.now(datetime.timezone.utc)
    return TranscriptSegment(
        text=text,
        speaker='SPEAKER_0',
        is_user=True,
        person_id=None,
        start=0.0,
        end=1.0,
        created_at=now,
    )


def test_punctuate_joined_text_and_maps_back(monkeypatch):
    monkeypatch.setenv('OMI_PUNCTUATE_ENABLED', 'true')
    segs = [_seg('xin chào bạn'), _seg('tôi là nam')]
    llm = MagicMock()
    # LLM contract: returns exactly N lines for N input segments.
    llm.invoke.return_value = MagicMock(content='Xin chào bạn.\nTôi là Nam.')
    with patch('utils.conversations.punctuation._get_llm', return_value=llm):
        from utils.conversations.punctuation import punctuate_segments

        out = punctuate_segments('uid', segs)
    assert [s.text for s in out] == ['Xin chào bạn.', 'Tôi là Nam.']


def test_fail_open_returns_original_on_llm_error(monkeypatch):
    monkeypatch.setenv('OMI_PUNCTUATE_ENABLED', 'true')
    segs = [_seg('không dấu')]
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError('provider down')
    with patch('utils.conversations.punctuation._get_llm', return_value=llm):
        from utils.conversations.punctuation import punctuate_segments

        out = punctuate_segments('uid', segs)
    assert [s.text for s in out] == ['không dấu']


def test_disabled_env_returns_original(monkeypatch):
    monkeypatch.setenv('OMI_PUNCTUATE_ENABLED', 'false')
    segs = [_seg('gốc')]
    with patch('utils.conversations.punctuation._get_llm') as m:
        from utils.conversations.punctuation import punctuate_segments

        out = punctuate_segments('uid', segs)
    m.assert_not_called()
    assert out[0].text == 'gốc'


def test_line_count_mismatch_fails_open(monkeypatch):
    monkeypatch.setenv('OMI_PUNCTUATE_ENABLED', 'true')
    segs = [_seg('mot'), _seg('hai')]
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content='Một dòng duy nhất.')
    with patch('utils.conversations.punctuation._get_llm', return_value=llm):
        from utils.conversations.punctuation import punctuate_segments

        out = punctuate_segments('uid', segs)
    assert [s.text for s in out] == ['mot', 'hai']
