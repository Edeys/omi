import pytest

from app.config import settings
from app.processing.memory_extractor import (
    build_extraction_prompt,
    extract_from_memory,
    parse_extraction,
)
from app.store.memory_store import MemoryStore

VALID_JSON = (
    '{"action_items": [{"text": "Mua sữa lúc 8h", "due_date": "2026-08-24T08:00:00"}, '
    '{"text": null, "due_date": null}], "notes": ["Khách hàng quan tâm giá"], "decisions": []}'
)


class FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list = []

    async def __call__(self, messages) -> str:
        self.calls.append(messages)
        return self.reply


@pytest.fixture
def store(tmp_path) -> MemoryStore:
    return MemoryStore(str(tmp_path / "mem"))


def test_parse_plain_json() -> None:
    out = parse_extraction(VALID_JSON)
    assert len(out["action_items"]) == 1
    assert out["action_items"][0]["text"] == "Mua sữa lúc 8h"
    assert out["notes"] == ["Khách hàng quan tâm giá"]


def test_parse_fenced_and_noisy_json() -> None:
    noisy = "Đây là kết quả:\n```json\n" + VALID_JSON + "\n```\nHết."
    out = parse_extraction(noisy)
    assert out["action_items"][0]["text"] == "Mua sữa lúc 8h"


def test_parse_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_extraction("không có json ở đây")


def test_string_action_items_normalized() -> None:
    out = parse_extraction('{"action_items": ["gọi điện cho A"], "notes": [], "decisions": []}')
    assert out["action_items"][0] == {"text": "gọi điện cho A", "due_date": None}


def test_prompt_contains_transcript_and_summary() -> None:
    messages = build_extraction_prompt("transcript body", "summary body")
    joined = messages[1]["content"]
    assert "transcript body" in joined and "summary body" in joined


@pytest.mark.asyncio
async def test_extract_persists_items(store: MemoryStore) -> None:
    llm = FakeLLM(VALID_JSON)
    memory = {"id": "m1", "transcript": "ban ghi noi chuyen", "summary": "tom tat"}
    result = await extract_from_memory("u1", memory, llm, store)
    assert result == {"action_items": 1, "notes": 1, "decisions": 0}
    actions = store.list_items("u1", kind="action_item")
    notes = store.list_items("u1", kind="note")
    assert actions[0]["due_date"] == "2026-08-24T08:00:00"
    assert actions[0]["done"] is False
    assert notes[0]["text"] == "Khách hàng quan tâm giá"


@pytest.mark.asyncio
async def test_extract_empty_memory_skips_llm(store: MemoryStore) -> None:
    llm = FakeLLM(VALID_JSON)
    result = await extract_from_memory("u2", {"id": "m2", "transcript": "", "summary": ""}, llm, store)
    assert result == {"action_items": 0, "notes": 0, "decisions": 0}
    assert llm.calls == []


@pytest.mark.asyncio
async def test_unparseable_output_saved_as_raw(store: MemoryStore) -> None:
    llm = FakeLLM("một câu trả lời không phải json")
    result = await extract_from_memory(
        "u3", {"id": "m3", "transcript": "noi dung", "summary": ""}, llm, store
    )
    assert result.get("fallback") is True
    raws = store.list_items("u3", kind="raw")
    assert raws and raws[0]["kind"] == "raw"


@pytest.mark.asyncio
async def test_forward_url_receives_payload(store: MemoryStore) -> None:
    sent: dict = {}

    async def fake_post(url, payload):
        sent["url"] = url
        sent["payload"] = payload

    llm = FakeLLM(VALID_JSON)
    await extract_from_memory(
        "u4",
        {"id": "m4", "transcript": "nd", "summary": "st"},
        llm,
        store,
        forward_url="https://n8n.example/hook",
        http_post=fake_post,
    )
    assert sent["url"] == "https://n8n.example/hook"
    assert sent["payload"]["extraction"]["notes"] == ["Khách hàng quan tâm giá"]


def test_store_list_filter_and_limit(store: MemoryStore) -> None:
    import asyncio

    async def seed():
        llm = FakeLLM(
            '{"action_items":[{"text":"viec 1","due_date":null},{"text":"viec 2","due_date":null}],'
            '"notes":["ghi chu"],"decisions":["quyet dinh"]}'
        )
        await extract_from_memory("u5", {"id": "m5", "transcript": "t", "summary": "s"}, llm, store)

    asyncio.run(seed())
    all_items = store.list_items("u5")
    assert len(all_items) == 4
    only_actions = store.list_items("u5", kind="action_item")
    assert {i["text"] for i in only_actions} == {"viec 1", "viec 2"}
