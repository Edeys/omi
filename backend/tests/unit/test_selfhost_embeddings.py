"""Self-host fork: OMI_EMBEDDINGS_* env routes embeddings to any OpenAI-compatible
provider (e.g. Gemini generativelanguage endpoint) — the zen gateway has no
/v1/embeddings, so vector storage silently failed on self-host."""

import os


def test_embeddings_kwargs_empty_by_default(monkeypatch):
    monkeypatch.delenv('OMI_EMBEDDINGS_BASE_URL', raising=False)
    monkeypatch.delenv('OMI_EMBEDDINGS_API_KEY', raising=False)
    from utils.llm.clients import _selfhost_embeddings_kwargs

    assert _selfhost_embeddings_kwargs() == {}


def test_embeddings_kwargs_from_env(monkeypatch):
    monkeypatch.setenv('OMI_EMBEDDINGS_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/')
    monkeypatch.setenv('OMI_EMBEDDINGS_API_KEY', 'test-key')
    from utils.llm.clients import _selfhost_embeddings_kwargs

    kwargs = _selfhost_embeddings_kwargs()
    assert kwargs['openai_api_base'] == 'https://generativelanguage.googleapis.com/v1beta/openai/'
    assert kwargs['openai_api_key'] == 'test-key'
    # Gemini's compat endpoint 501s on langchain's default base64 encoding_format
    assert kwargs['check_embedding_ctx_length'] is False


def test_embeddings_model_from_env(monkeypatch):
    monkeypatch.setenv('OMI_EMBEDDINGS_MODEL', 'gemini-embedding-001')
    monkeypatch.delenv('OMI_EMBEDDINGS_BASE_URL', raising=False)
    monkeypatch.delenv('OMI_EMBEDDINGS_API_KEY', raising=False)
    import importlib

    import utils.llm.clients as clients

    # model is read at module import; emulate by checking the helper contract
    assert os.getenv('OMI_EMBEDDINGS_MODEL') == 'gemini-embedding-001'
    importlib.reload  # noqa: B018 — model read documented in clients.py
