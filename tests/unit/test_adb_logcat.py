from unittest.mock import patch, MagicMock

def test_adb_logcat_filters_package(monkeypatch):
    fake_output = (
        "08-25 14:36:19.459 W/Auth: Server returned error\n"
        "08-25 14:36:19.559 I/flutter: OAuth Google sign in error\n"
        "08-25 14:36:20.000 D/OtherApp: Normal background noise\n"
    )
    mock_run = MagicMock(return_value=MagicMock(stdout=fake_output.encode()))
    with patch("subprocess.run", mock_run):
        from tools.adb_logcat import fetch_logcat
        out = fetch_logcat(package="com.friend.ios.dev", filters=["Auth", "flutter"], since_seconds=60)
        assert "Auth" in out
        assert "flutter" in out
        assert "OtherApp" not in out

def test_check_adb_device_parses_authorized():
    from tools.check_adb_device import parse_devices_output
    sample = "List of devices attached\n9B061FFAZ00E5C       device product:flame model:Pixel_4 device:flame transport_id:2"
    assert parse_devices_output(sample) == [{"id": "9B061FFAZ00E5C", "state": "device", "model": "Pixel_4"}]
