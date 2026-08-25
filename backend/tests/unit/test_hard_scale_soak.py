from unittest.mock import MagicMock, patch

def test_mint_custom_token_uses_firebase_admin(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/firebase-service-account.json")
    fake_token = b"fake.jwt.token"
    with patch("firebase_admin.auth.create_custom_token", return_value=fake_token) as mock_create:
        from selfhost.scripts.soak_real_auth import mint_custom_token
        token = mint_custom_token("test-uid")
        assert token == fake_token
        mock_create.assert_called_once_with("test-uid")

def test_soak_config_defaults():
    from selfhost.scripts.soak_real_auth import SoakConfig
    cfg = SoakConfig(users=5, duration=600)
    assert cfg.ramp_seconds == 60
    assert cfg.silence_interval == 5.0
