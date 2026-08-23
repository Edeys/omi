import json
import os
import threading
from typing import Any

_lock = threading.Lock()


class MemoryStore:
    """Append-only JSONL store of extracted items, per user, on a Docker volume."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def _path(self, uid: str) -> str:
        safe = "".join(c for c in uid if c.isalnum() or c in "-_")[:64] or "unknown"
        directory = os.path.join(self.base_dir, safe)
        os.makedirs(directory, exist_ok=True)
        return os.path.join(directory, "items.jsonl")

    def append(self, uid: str, record: dict[str, Any]) -> int:
        path = self._path(uid)
        with _lock:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return self.count(uid)

    def list_items(self, uid: str, kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        path = self._path(uid)
        if not os.path.exists(path):
            return []
        out: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if kind and item.get("kind") != kind:
                    continue
                out.append(item)
        return out[-limit:]

    def count(self, uid: str) -> int:
        return len(self.list_items(uid))
