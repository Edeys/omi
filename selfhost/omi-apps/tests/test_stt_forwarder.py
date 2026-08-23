import json

import pytest

from app.stt.forwarder import transcribe_pcm


class FakeWS:
    def __init__(self) -> None:
        self.sent: list = []
        self.results: list[str] = []
        self.closed = False

    async def send(self, data) -> None:
        self.sent.append(data)

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def recv(self):
        if self.results:
            return self.results.pop(0)
        raise StopAsyncIteration


def _result(text: str, is_final: bool = True, from_finalize: bool = False) -> str:
    return json.dumps(
        {
            "type": "Results",
            "channel": {"alternatives": [{"transcript": text}]},
            "is_final": is_final,
            "from_finalize": from_finalize,
        }
    )


@pytest.mark.asyncio
async def test_transcribe_streams_and_collects_finals() -> None:
    ws = FakeWS()
    ws.results = [
        json.dumps({"type": "Metadata"}),
        _result("xin chao"),
        _result("theoi gioi"),
    ]

    async def connect():
        return ws

    pcm = b"\x00\x00" * 4800
    out = await transcribe_pcm(pcm, connect, frame_bytes=3200)
    assert out == "xin chao theoi gioi"
    starts = [s for s in ws.sent if isinstance(s, str) and s.startswith("{")]
    first = json.loads(starts[0])
    assert first["type"] == "Start"
    assert first["sample_rate"] == 16000
    assert any(json.loads(s).get("type") == "CloseStream" for s in starts)
    binary = [s for s in ws.sent if isinstance(s, bytes)]
    assert sum(len(b) for b in binary) == len(pcm)


@pytest.mark.asyncio
async def test_error_frame_stops_collection() -> None:
    ws = FakeWS()
    ws.results = [
        json.dumps({"type": "Error", "message": "bad frame"}),
        _result("khong nen doc"),
    ]

    async def connect():
        return ws

    out = await transcribe_pcm(b"\x00\x00\x00\x00", connect)
    assert out == ""
