"""Self-host fork: OMI_STRUCTURED_METHOD forces langchain's structured-output method.

Reasoning models behind OpenAI-compatible gateways (e.g. ox-alpha-free via zen)
ignore json_schema response_format and answer in prose, breaking every
`.with_structured_output()` caller — conversation processing failed with
BadRequestError/parse errors on every capture. function_calling works with the
same model (verified live 2026-08-24). Upstream behaviour when env unset.
"""

from unittest.mock import patch


def _make_instance():
    from utils.llm.providers import SelfHostStructuredChatOpenAI

    return SelfHostStructuredChatOpenAI(model='test-model', api_key='sk-test')


def test_env_set_forces_method(monkeypatch):
    monkeypatch.setenv('OMI_STRUCTURED_METHOD', 'function_calling')
    inst = _make_instance()
    captured = {}

    def fake_base(self, schema, *args, **kwargs):
        captured.update(kwargs)
        return 'sentinel'

    with patch('langchain_openai.ChatOpenAI.with_structured_output', new=fake_base):
        out = inst.with_structured_output(schema=object())
    assert captured.get('method') == 'function_calling'
    assert out == 'sentinel'


def test_env_set_does_not_override_explicit_method(monkeypatch):
    monkeypatch.setenv('OMI_STRUCTURED_METHOD', 'function_calling')
    inst = _make_instance()
    captured = {}

    def fake_base(self, schema, *args, **kwargs):
        captured.update(kwargs)
        return 'sentinel'

    with patch('langchain_openai.ChatOpenAI.with_structured_output', new=fake_base):
        inst.with_structured_output(schema=object(), method='json_schema')
    assert captured.get('method') == 'json_schema'


def test_env_unset_keeps_upstream_default(monkeypatch):
    monkeypatch.delenv('OMI_STRUCTURED_METHOD', raising=False)
    inst = _make_instance()
    captured = {}

    def fake_base(self, schema, *args, **kwargs):
        captured.update(kwargs)
        return 'sentinel'

    with patch('langchain_openai.ChatOpenAI.with_structured_output', new=fake_base):
        inst.with_structured_output(schema=object())
    assert 'method' not in captured


def test_openai_provider_uses_selfhost_class(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')
    monkeypatch.delenv('OPENAI_BASE_URL', raising=False)
    monkeypatch.delenv('OPENROUTER_BASE_URL', raising=False)
    from utils.llm import providers
    from utils.llm.providers import SelfHostStructuredChatOpenAI, _llm_cache

    _llm_cache.clear()
    llm = providers.get_or_create_openai_compatible_llm('openai', 'some-model')
    assert isinstance(llm, SelfHostStructuredChatOpenAI)
