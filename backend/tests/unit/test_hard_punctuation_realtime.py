from unittest.mock import MagicMock, patch

def test_punctuate_text_realtime_success(monkeypatch):
    monkeypatch.setenv("OMI_PUNCTUATE_REALTIME", "true")
    llm = MagicMock()
    llm.invoke.return_value.content = "Xin chào bạn. Tôi là Nam."
    with patch("backend.utils.stt.punctuation_llm._get_llm", return_value=llm):
        from backend.utils.stt.punctuation_llm import punctuate_text_realtime
        assert punctuate_text_realtime("xin chào bạn tôi là nam", language="vi") == "Xin chào bạn. Tôi là Nam."

def test_punctuate_text_realtime_fail_open(monkeypatch):
    monkeypatch.setenv("OMI_PUNCTUATE_REALTIME", "true")
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError("provider down")
    with patch("backend.utils.stt.punctuation_llm._get_llm", return_value=llm):
        from backend.utils.stt.punctuation_llm import punctuate_text_realtime
        assert punctuate_text_realtime("không dấu", language="vi") == "không dấu"

def test_punctuate_text_realtime_disabled_returns_input(monkeypatch):
    monkeypatch.setenv("OMI_PUNCTUATE_REALTIME", "false")
    from backend.utils.stt.punctuation_llm import punctuate_text_realtime
    with patch("backend.utils.stt.punctuation_llm._get_llm") as mock_get:
        assert punctuate_text_realtime("giữ nguyên", language="vi") == "giữ nguyên"
        mock_get.assert_not_called()
