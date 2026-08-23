import os

import pytest

from app.store.audio import AudioStore, wav_header


@pytest.fixture
def store(tmp_path) -> AudioStore:
    return AudioStore(str(tmp_path / "audio"), idle_finalize_seconds=300)


def test_wav_header_structure() -> None:
    header = wav_header(num_samples=16000, sample_rate=16000)
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"
    assert header[12:16] == b"fmt "
    assert header[36:40] == b"data"
    data_size = int.from_bytes(header[40:44], "little")
    assert data_size == 32000
    riff_size = int.from_bytes(header[4:8], "little")
    assert riff_size == 36 + 32000


def test_append_creates_file_and_meta(store: AudioStore) -> None:
    info = store.append_chunk("user1", b"\x01\x02\x03\x04", sample_rate=16000)
    assert info["new_file"] is True
    pcm = info["path"]
    assert os.path.exists(pcm)
    assert os.path.exists(pcm + ".json")
    with open(pcm, "rb") as fh:
        assert fh.read() == b"\x01\x02\x03\x04"


def test_append_appends_same_slot(store: AudioStore) -> None:
    store.append_chunk("user1", b"\x00\x00", 16000)
    info2 = store.append_chunk("user1", b"\xff\xff", 16000)
    assert info2["new_file"] is False
    size = os.path.getsize(info2["path"])
    assert size == 4


def test_stale_detection_and_finalize(store: AudioStore) -> None:
    import time

    info = store.append_chunk("u9", b"\x10\x10" * 100, 8000, now=time.time())
    assert store.stale_open_files("u9") == []
    old = time.time() - 400
    os.utime(info["path"], (old, old))
    stale = store.stale_open_files("u9")
    assert len(stale) == 1
    wav_path = store.finalize(stale[0])
    assert wav_path is not None and wav_path.endswith(".wav")
    with open(wav_path, "rb") as fh:
        blob = fh.read()
    assert blob[:4] == b"RIFF" and blob[36:40] == b"data"
    assert len(blob) == 44 + 200
    assert not os.path.exists(info["path"])
    assert not os.path.exists(info["path"] + ".json")


def test_list_and_read_wav(store: AudioStore) -> None:
    info = store.append_chunk("uL", b"\x20\x20" * 50, 16000)
    store.finalize(info["path"])
    files = store.list_audio("uL")
    names = [f["name"] for f in files]
    assert any(n.endswith(".wav") for n in names)
    wav_name = [n for n in names if n.endswith(".wav")][0]
    blob = store.read_wav("uL", wav_name)
    assert blob is not None and blob[:4] == b"RIFF"
    assert store.read_wav("uL", "../escape.wav") is None
