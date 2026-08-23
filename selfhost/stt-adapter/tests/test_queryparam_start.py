import json
from fastapi.testclient import TestClient
import main
from conftest import ScriptedRecognizer

def test_queryparam_auto_start_accepts_binary_without_json_start():
    main.set_recognizer_factory(lambda: ScriptedRecognizer(
        segments=[{"text": "xin chào", "is_final": True, "start": 0.0, "duration": 0.5}]
    ))
    client = TestClient(main.app)
    with client.websocket_connect("/v1/listen?sample_rate=16000&encoding=linear16&channels=1&language=vi&model=nova-3") as ws:
        ws.send_bytes(b"\x00\x00" * 8000)
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "Results"
        assert msg["channel"]["alternatives"][0]["transcript"] == "xin chào"
