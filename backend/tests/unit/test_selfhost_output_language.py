"""Self-host: OMI_FORCE_OUTPUT_LANGUAGE ép ngôn ngữ output (title/tóm tắt)
khi app gửi language=en nhưng user nói tiếng Việt."""

from unittest.mock import patch

import utils.conversations.process_conversation as pc


def test_force_env_overrides_everything(monkeypatch):
    monkeypatch.setenv('OMI_FORCE_OUTPUT_LANGUAGE', 'vi')
    with patch.object(pc.users_db, 'get_user_language_preference', return_value='en'):
        assert pc._effective_output_language('uid', 'en') == 'vi'


def test_no_env_keeps_user_preference(monkeypatch):
    monkeypatch.delenv('OMI_FORCE_OUTPUT_LANGUAGE', raising=False)
    with patch.object(pc.users_db, 'get_user_language_preference', return_value='en'):
        assert pc._effective_output_language('uid', 'en') == 'en'


def test_no_env_no_preference_falls_back_to_language_code(monkeypatch):
    monkeypatch.delenv('OMI_FORCE_OUTPUT_LANGUAGE', raising=False)
    with patch.object(pc.users_db, 'get_user_language_preference', return_value=None):
        assert pc._effective_output_language('uid', 'vi') == 'vi'
