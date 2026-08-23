"""Embedded SQLite+numpy vector index.

Implements exactly the Pinecone Index subset that ``database/vector_db.py``
exercises (upsert / query / update / delete / list) so it can stand in as the
module-level ``index`` handle when Pinecone is not configured. This is the
self-hosted backend path: no extra container, data persists in one WAL-mode
SQLite file under a compose volume.

Filter grammar (Pinecone-compatible, operators actually used in the repo):
- scalar value            -> implicit $eq
- {'$eq': v} {'$ne': v}   -> equality / inequality; array metadata matches if
                             it CONTAINS the operand (Pinecone semantics)
- {'$in': [..]}           -> membership; array metadata matches on intersection
- {'$gte': v} {'$lte': v} -> numeric/date comparisons
- {'$and': [filters]} {'$or': [filters]} -> nested filter lists

Scale note: brute-force cosine over one namespace is intentional — a personal
deployment holds thousands, not millions, of vectors. Rows are cached per
namespace in-process; every write invalidates that namespace's cache.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from typing import Any, Dict, Iterator, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vectors (
    namespace TEXT NOT NULL,
    id TEXT NOT NULL,
    vec BLOB NOT NULL,
    metadata TEXT NOT NULL,
    PRIMARY KEY (namespace, id)
)
"""


def _pack(values: Sequence[float]) -> bytes:
    return np.asarray(list(values), dtype=np.float32).tobytes()


def _unpack(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def _escape_like(prefix: str) -> str:
    return prefix.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _eq(actual: Any, expected: Any) -> bool:
    if isinstance(actual, list):
        return expected in actual
    return actual == expected


class LocalVectorIndex:
    """Drop-in replacement for the Pinecone Index calls vector_db.py makes."""

    def __init__(self, path: str):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.execute('PRAGMA synchronous=NORMAL')
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        # namespace -> None (dirty) or (ids list, float32 matrix, metadata dicts)
        self._cache: Dict[str, Optional[tuple]] = {}

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _invalidate(self, namespace: str) -> None:
        self._cache[namespace] = None

    def _namespace_rows(self, namespace: str) -> tuple:
        cached = self._cache.get(namespace)
        if cached is not None:
            return cached
        cursor = self._conn.execute(
            'SELECT id, vec, metadata FROM vectors WHERE namespace = ? ORDER BY id', (namespace,)
        )
        ids: List[str] = []
        meta: List[Dict[str, Any]] = []
        blobs: List[bytes] = []
        for row_id, blob, metadata_json in cursor:
            ids.append(row_id)
            blobs.append(blob)
            meta.append(json.loads(metadata_json))
        matrix = np.stack([_unpack(b) for b in blobs]) if blobs else np.zeros((0, 1), dtype=np.float32)
        entry = (ids, matrix, meta)
        self._cache[namespace] = entry
        return entry

    @classmethod
    def _match_value(cls, actual: Any, condition: Any) -> bool:
        if isinstance(condition, dict):
            for op, operand in condition.items():
                if op == '$eq':
                    if not _eq(actual, operand):
                        return False
                elif op == '$ne':
                    if _eq(actual, operand):
                        return False
                elif op == '$in':
                    if isinstance(actual, list):
                        if not any(item in actual for item in operand):
                            return False
                    elif actual not in operand:
                        return False
                elif op == '$gte':
                    if actual is None or actual < operand:
                        return False
                elif op == '$lte':
                    if actual is None or actual > operand:
                        return False
                else:
                    raise ValueError(f'Unsupported filter operator: {op}')
            return True
        return _eq(actual, condition)

    @classmethod
    def _matches(cls, metadata: Dict[str, Any], flt: Any) -> bool:
        if not flt:
            return True
        for key, condition in flt.items():
            if key == '$and':
                if not all(cls._matches(metadata, sub) for sub in condition):
                    return False
            elif key == '$or':
                if not any(cls._matches(metadata, sub) for sub in condition):
                    return False
            elif key.startswith('$'):
                raise ValueError(f'Unsupported filter operator: {key}')
            elif not cls._match_value(metadata.get(key), condition):
                return False
        return True

    # ------------------------------------------------------------------ #
    # Pinecone-compatible surface
    # ------------------------------------------------------------------ #
    def upsert(self, *, vectors: List[Dict[str, Any]], namespace: Optional[str] = None) -> Dict[str, Any]:
        ns = namespace or ''
        with self._lock:
            with self._conn:
                for record in vectors:
                    self._conn.execute(
                        'INSERT OR REPLACE INTO vectors (namespace, id, vec, metadata) VALUES (?, ?, ?, ?)',
                        (ns, record['id'], _pack(record['values']), json.dumps(record.get('metadata') or {})),
                    )
            self._invalidate(ns)
        return {'upserted_count': len(vectors)}

    def query(
        self,
        *,
        vector: Sequence[float],
        top_k: int = 10,
        include_metadata: bool = False,
        include_values: bool = False,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        ns = namespace or ''
        with self._lock:
            ids, matrix, meta = self._namespace_rows(ns)

        keep: List[int] = []
        if matrix.shape[0]:
            q = np.asarray(vector, dtype=np.float32)
            for i, stored_meta in enumerate(meta):
                if filter and not self._matches(stored_meta, filter):
                    continue
                keep.append(i)

        matches: List[Dict[str, Any]] = []
        if keep:
            sub_matrix = matrix[keep]
            norms = np.linalg.norm(sub_matrix, axis=1)
            q_norm = float(np.linalg.norm(q))
            denom = norms * q_norm
            safe_denom = np.where(denom == 0.0, 1.0, denom)
            scores = np.where(denom == 0.0, 0.0, (sub_matrix @ q) / safe_denom)
            order = np.argsort(-scores)[: max(1, top_k)]
            for local_i in order:
                i = keep[int(local_i)]
                match: Dict[str, Any] = {'id': ids[i], 'score': float(scores[int(local_i)])}
                if include_metadata:
                    match['metadata'] = dict(meta[i])
                if include_values:
                    match['values'] = matrix[i].tolist()
                matches.append(match)
        return {'matches': matches}

    def update(self, id: str, *, set_metadata: Dict[str, Any], namespace: Optional[str] = None) -> Dict[str, Any]:
        ns = namespace or ''
        with self._lock:
            row = self._conn.execute('SELECT metadata FROM vectors WHERE namespace = ? AND id = ?', (ns, id)).fetchone()
            if row is None:
                raise KeyError(f'vector {id!r} not found in namespace {ns!r}')
            merged = json.loads(row[0])
            merged.update(set_metadata)
            with self._conn:
                self._conn.execute(
                    'UPDATE vectors SET metadata = ? WHERE namespace = ? AND id = ?',
                    (json.dumps(merged), ns, id),
                )
            self._invalidate(ns)
        return {'id': id}

    def delete(
        self,
        *,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
        delete_all: bool = False,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        ns = namespace or ''
        with self._lock:
            if delete_all:
                with self._conn:
                    self._conn.execute('DELETE FROM vectors WHERE namespace = ?', (ns,))
            elif ids:
                placeholders = ','.join('?' * len(ids))
                with self._conn:
                    self._conn.execute(
                        f'DELETE FROM vectors WHERE namespace = ? AND id IN ({placeholders})',
                        (ns, *ids),
                    )
            elif filter is not None:
                victim_ids = [
                    row[0]
                    for row in self._conn.execute(
                        'SELECT id, metadata FROM vectors WHERE namespace = ?', (ns,)
                    ).fetchall()
                    if self._matches(json.loads(row[1]), filter)
                ]
                if victim_ids:
                    placeholders = ','.join('?' * len(victim_ids))
                    with self._conn:
                        self._conn.execute(
                            f'DELETE FROM vectors WHERE namespace = ? AND id IN ({placeholders})',
                            (ns, *victim_ids),
                        )
            else:
                raise ValueError('delete requires ids, filter, or delete_all')
            self._invalidate(ns)
        return {}

    def list(
        self, *, prefix: Optional[str] = None, namespace: Optional[str] = None, limit: int = _PAGE_SIZE
    ) -> Iterator[List[str]]:
        """Yield pages of at most ``limit`` ids, mirroring Pinecone's paginated iterator."""
        ns = namespace or ''
        like = f'{_escape_like(prefix or "")}%'
        offset = 0
        while True:
            rows = self._conn.execute(
                "SELECT id FROM vectors WHERE namespace = ? AND id LIKE ? ESCAPE '\\' ORDER BY id LIMIT ? OFFSET ?",
                (ns, like, limit, offset),
            ).fetchall()
            page = [row[0] for row in rows]
            if not page:
                return
            yield page
            offset += len(page)
