from unittest.mock import MagicMock, patch

def test_ensure_bucket_returns_false_when_not_configured(monkeypatch):
    monkeypatch.delenv("BUCKET_SPEECH_PROFILES", raising=False)
    from backend.utils.other.storage import ensure_speech_profile_bucket
    assert ensure_speech_profile_bucket("uid") is False

def test_ensure_bucket_checks_gcs_when_configured(monkeypatch):
    monkeypatch.setenv("BUCKET_SPEECH_PROFILES", "my-bucket")
    fake_bucket = MagicMock()
    fake_bucket.exists.return_value = True
    fake_client = MagicMock()
    fake_client.bucket.return_value = fake_bucket
    # storage module is imported as backend.utils.other.storage when running from repo root
    import backend.utils.other.storage as storage_mod
    # module caches BUCKET var at import time; patch it too for env change
    monkeypatch.setattr(storage_mod, "speech_profiles_bucket", "my-bucket", raising=False)
    with patch.object(storage_mod, "_get_storage_client", return_value=fake_client):
        assert storage_mod.ensure_speech_profile_bucket("uid") is True
        fake_client.bucket.assert_called_once_with("my-bucket")
