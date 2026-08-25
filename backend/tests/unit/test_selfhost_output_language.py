"""Self-host: OMI_FORCE_OUTPUT_LANGUAGE ép ngôn ngữ output (title/tóm tắt)
khi app gửi language=en nhưng user nói tiếng Việt.

Dùng sys.modules stubs để import utils.conversations.process_conversation
mà không chạm Firestore/Firebase init (theo pattern test_lazy_conversation_processing).
"""
import sys
import types

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def pc_module(monkeypatch):
    monkeypatch.delenv('OMI_FORCE_OUTPUT_LANGUAGE', raising=False)

    def _stub(name):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
        return sys.modules[name]

    saved = {}
    stubs = [
        'google.cloud',
        'google.cloud.firestore',
        'google.cloud.firestore_v1',
        'google.cloud.firestore_v1.base_query',
        'google.cloud.exceptions',
        'google.cloud.storage',
        'firebase_admin',
        'firebase_admin.auth',
        'firebase_admin.firestore',
        'database._client',
        'database.redis_db',
        'database.users',
        'database.conversations',
        'database.notifications',
        'database.tasks',
        'database.action_items',
        'database.folders',
        'database.calendar_meetings',
        'database.screen_activity',
        'database.vector_db',
        'database.apps',
        'prometheus_client',
        'utils.metrics',
        'langchain_openai',
        'langchain_core',
        'langchain_core.callbacks',
        'langchain_core.messages',
        'langchain_core.outputs',
        'langchain_core.language_models',
        'langchain_core.output_parsers',
        'langchain_core.prompts',
        'langchain_core.runnables',
        'langchain_core.tools',
        'langchain_google_genai',
        'anthropic',
        'stripe',
        'pycountry',
        'ulid',
    ]
    for name in stubs:
        saved[name] = sys.modules.get(name)
        if name == 'prometheus_client':
            pm = MagicMock()
            pm.CONTENT_TYPE_LATEST = 'text/plain'
            sys.modules[name] = pm
            continue
        if name == 'google.cloud.firestore_v1':
            fv1 = types.ModuleType('google.cloud.firestore_v1')
            fv1.FieldFilter = MagicMock()
            fv1.LastUpdateOption = MagicMock()
            fv1.Query = MagicMock()
            fv1.transactional = MagicMock()
            bq = types.ModuleType('google.cloud.firestore_v1.base_query')
            bq.FieldFilter = MagicMock()
            fv1.base_query = bq
            sys.modules[name] = fv1
            continue
        # MagicMock as module: attribute access auto-creates, so both
        # `from X import y` and `X.func(...)` work without real backends.
        sys.modules[name] = MagicMock()

    udb = sys.modules['database.users']
    udb.get_user_language_preference.return_value = None

    # Drop cached copies of the package under test so stubs take effect.
    for name in list(sys.modules):
        if name.startswith('utils.conversations'):
            del sys.modules[name]

    import utils.conversations.process_conversation as pc
    yield pc

    for name, mod in saved.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod
    for name in list(sys.modules):
        if name.startswith('utils.conversations'):
            del sys.modules[name]


def test_force_env_overrides_everything(pc_module, monkeypatch):
    monkeypatch.setenv('OMI_FORCE_OUTPUT_LANGUAGE', 'vi')
    with patch_lang_pref(pc_module, 'en'):
        assert pc_module._effective_output_language('uid', 'en') == 'vi'


def test_no_env_keeps_user_preference(pc_module, monkeypatch):
    monkeypatch.delenv('OMI_FORCE_OUTPUT_LANGUAGE', raising=False)
    with patch_lang_pref(pc_module, 'en'):
        assert pc_module._effective_output_language('uid', 'en') == 'en'


def test_no_env_no_preference_falls_back_to_language_code(pc_module, monkeypatch):
    monkeypatch.delenv('OMI_FORCE_OUTPUT_LANGUAGE', raising=False)
    assert pc_module._effective_output_language('uid', 'vi') == 'vi'


def patch_lang_pref(pc_module, value):
    from unittest.mock import patch
    return patch.object(pc_module.users_db, 'get_user_language_preference', return_value=value)
