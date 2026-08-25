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
    with patch("backend.utils.other.storage._get_storage_client", return_value=fake_client):
        from backend.utils.other.storage import ensure_speech_profile_bucket
        assert ensure_speech_profile_bucket("uid") is True
        fake_client.bucket.assert_called_once_with("my-bucket")
