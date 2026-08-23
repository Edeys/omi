"""LocalVectorIndex — embedded SQLite+numpy replacement for the Pinecone subset
that database/vector_db.py uses (upsert/query/update/delete/list).

Contract under test:
- query() returns {'matches': [{'id', 'score', 'metadata'?}]} with scores sorted desc
- filters support $eq, $in, $gte, $lte, $and, $or (implicit $eq for scalar values)
  with Pinecone array semantics: an array metadata value matches if it contains the operand
- list(prefix, namespace) yields pages of at most 100 ids

Integration tests load database.vector_db fresh via the sanctioned Tier-2 pattern
(testing/import_isolation, see test_action_item_dedup.py) and point its module-level
``index`` handle at a LocalVectorIndex to prove end-to-end compatibility.
"""

import os
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from testing.import_isolation import load_module_fresh, stub_modules

_BACKEND = Path(__file__).resolve().parents[2]

DIM = 4


def _vec(x):
    base = [0.0] * DIM
    base[0] = x
    return base


@pytest.fixture()
def idx(tmp_path):
    from database.local_vector_index import LocalVectorIndex

    return LocalVectorIndex(path=str(tmp_path / 'vectors.sqlite3'))


class TestUpsertQueryBasics:
    def test_cosine_order_and_uid_eq_filter(self, idx):
        idx.upsert(
            vectors=[
                {'id': 'u1-c1', 'values': [1.0, 0.0, 0.0, 0.0], 'metadata': {'uid': 'u1'}},
                {'id': 'u1-c2', 'values': [0.9, 0.1, 0.0, 0.0], 'metadata': {'uid': 'u1'}},
                {'id': 'u2-c1', 'values': [1.0, 0.0, 0.0, 0.0], 'metadata': {'uid': 'u2'}},
            ],
            namespace='ns1',
        )
        res = idx.query(
            vector=[1.0, 0.0, 0.0, 0.0],
            top_k=2,
            include_metadata=False,
            filter={'uid': 'u1'},
            namespace='ns1',
        )
        assert [m['id'] for m in res['matches']] == ['u1-c1', 'u1-c2']
        assert all('score' in m for m in res['matches'])
        assert res['matches'][0]['score'] >= res['matches'][1]['score']

    def test_scores_sorted_descending_and_topk_respected(self, idx):
        idx.upsert(
            vectors=[{'id': f'c{i}', 'values': _vec(1.0 - i * 0.1), 'metadata': {}} for i in range(5)],
            namespace='ns1',
        )
        res = idx.query(vector=_vec(1.0), top_k=3, include_metadata=False, namespace='ns1')
        scores = [m['score'] for m in res['matches']]
        assert len(scores) == 3
        assert scores == sorted(scores, reverse=True)

    def test_include_metadata_returns_copy(self, idx):
        idx.upsert(vectors=[{'id': 'a', 'values': _vec(1.0), 'metadata': {'uid': 'u'}}], namespace='ns1')
        res = idx.query(vector=_vec(1.0), top_k=5, include_metadata=True, namespace='ns1')
        assert res['matches'][0]['metadata'] == {'uid': 'u'}

    def test_include_values_kwarg_accepted(self, idx):
        idx.upsert(vectors=[{'id': 'a', 'values': _vec(1.0), 'metadata': {}}], namespace='ns1')
        res = idx.query(vector=_vec(1.0), top_k=5, include_values=False, include_metadata=True, namespace='ns1')
        assert res['matches'][0]['id'] == 'a'


class TestFilters:
    def test_created_at_range_gte_lte(self, idx):
        idx.upsert(
            vectors=[
                {'id': 'old', 'values': _vec(1.0), 'metadata': {'created_at': 100}},
                {'id': 'mid', 'values': _vec(1.0), 'metadata': {'created_at': 150}},
                {'id': 'new', 'values': _vec(1.0), 'metadata': {'created_at': 200}},
            ],
            namespace='ns1',
        )
        res = idx.query(
            vector=_vec(1.0),
            top_k=10,
            include_metadata=False,
            filter={'created_at': {'$gte': 120, '$lte': 180}},
            namespace='ns1',
        )
        assert [m['id'] for m in res['matches']] == ['mid']

    def test_in_or_and_shape_from_query_vectors_by_metadata(self, idx):
        # Mirrors the exact filter shape built by vector_db.query_vectors_by_metadata.
        filter_data = {
            '$and': [
                {'uid': {'$eq': 'u1'}},
                {
                    '$or': [
                        {'people': {'$in': ['alice']}},
                        {'topics': {'$in': ['hiking']}},
                        {'entities': {'$in': []}},
                    ]
                },
            ]
        }
        idx.upsert(
            vectors=[
                {'id': 'hit', 'values': _vec(1.0), 'metadata': {'uid': 'u1', 'people': ['alice']}},
                {'id': 'hit-topic', 'values': _vec(1.0), 'metadata': {'uid': 'u1', 'topics': ['hiking']}},
                {'id': 'wrong-uid', 'values': _vec(1.0), 'metadata': {'uid': 'u2', 'people': ['alice']}},
                {'id': 'no-match', 'values': _vec(1.0), 'metadata': {'uid': 'u1', 'people': ['bob']}},
            ],
            namespace='ns1',
        )
        res = idx.query(vector=_vec(1.0), top_k=100, include_metadata=False, filter=filter_data, namespace='ns1')
        assert sorted(m['id'] for m in res['matches']) == ['hit', 'hit-topic']

    def test_array_membership_semantics_for_eq_and_in(self, idx):
        idx.upsert(
            vectors=[
                {'id': 'has-a', 'values': _vec(1.0), 'metadata': {'tags': ['a', 'b']}},
                {'id': 'no-a', 'values': _vec(1.0), 'metadata': {'tags': ['c']}},
            ],
            namespace='ns1',
        )
        for f in ({'tags': 'a'}, {'tags': {'$eq': 'a'}}, {'tags': {'$in': ['a', 'z']}}):
            res = idx.query(vector=_vec(1.0), top_k=10, include_metadata=False, filter=f, namespace='ns1')
            assert [m['id'] for m in res['matches']] == ['has-a'], f'filter {f}'


class TestUpdateDeleteList:
    def test_update_set_metadata_then_query_with_metadata(self, idx):
        idx.upsert(vectors=[{'id': 'a', 'values': _vec(1.0), 'metadata': {'uid': 'u'}}], namespace='ns1')
        result = idx.update('a', set_metadata={'topics': ['work']}, namespace='ns1')
        assert isinstance(result, dict)
        res = idx.query(vector=_vec(1.0), top_k=5, include_metadata=True, namespace='ns1')
        meta = res['matches'][0]['metadata']
        assert meta['topics'] == ['work']
        assert meta['uid'] == 'u'  # merge, not replace

    def test_update_missing_id_raises(self, idx):
        with pytest.raises(Exception):
            idx.update('ghost', set_metadata={'x': 1}, namespace='ns1')

    def test_delete_by_ids(self, idx):
        idx.upsert(
            vectors=[
                {'id': 'a', 'values': _vec(1.0), 'metadata': {}},
                {'id': 'b', 'values': _vec(1.0), 'metadata': {}},
            ],
            namespace='ns1',
        )
        idx.delete(ids=['a'], namespace='ns1')
        res = idx.query(vector=_vec(1.0), top_k=10, include_metadata=False, namespace='ns1')
        assert [m['id'] for m in res['matches']] == ['b']

    def test_delete_by_filter(self, idx):
        idx.upsert(
            vectors=[
                {'id': 'keep', 'values': _vec(1.0), 'metadata': {'uid': 'u1', 'status': 'active'}},
                {'id': 'drop', 'values': _vec(1.0), 'metadata': {'uid': 'u1', 'status': 'archived'}},
            ],
            namespace='ns1',
        )
        idx.delete(filter={'status': {'$eq': 'archived'}}, namespace='ns1')
        res = idx.query(vector=_vec(1.0), top_k=10, include_metadata=False, namespace='ns1')
        assert [m['id'] for m in res['matches']] == ['keep']

    def test_namespace_isolation(self, idx):
        idx.upsert(vectors=[{'id': 'a', 'values': _vec(1.0), 'metadata': {}}], namespace='ns1')
        res_other = idx.query(vector=_vec(1.0), top_k=10, include_metadata=False, namespace='ns2')
        assert res_other['matches'] == []
        idx.delete(ids=['a'], namespace='ns2')  # must not touch ns1
        res = idx.query(vector=_vec(1.0), top_k=10, include_metadata=False, namespace='ns1')
        assert len(res['matches']) == 1

    def test_list_prefix_pagination_max_100_per_page(self, idx):
        ids = [f'{i:04d}-x' for i in range(250)]
        idx.upsert(vectors=[{'id': i, 'values': _vec(1.0), 'metadata': {}} for i in ids], namespace='chunks')
        pages = list(idx.list(prefix='', namespace='chunks'))
        assert sum(len(p) for p in pages) == 250
        assert all(len(p) <= 100 for p in pages)
        assert [i for page in pages for i in page] == sorted(ids)
        pages_prefixed = list(idx.list(prefix='01', namespace='chunks'))
        assert [i for page in pages_prefixed for i in page] == [i for i in ids if i.startswith('01')]

    def test_upsert_same_id_replaces(self, idx):
        idx.upsert(vectors=[{'id': 'a', 'values': _vec(1.0), 'metadata': {'v': 1}}], namespace='ns1')
        idx.upsert(vectors=[{'id': 'a', 'values': _vec(1.0), 'metadata': {'v': 2}}], namespace='ns1')
        res = idx.query(vector=_vec(1.0), top_k=10, include_metadata=True, namespace='ns1')
        assert len(res['matches']) == 1
        assert res['matches'][0]['metadata']['v'] == 2


def _load_vector_db_fresh():
    """Sanctioned Tier-2 loading — stub heavy transitive deps before exec."""
    pinecone_stub = ModuleType('pinecone')
    pinecone_stub.Pinecone = MagicMock

    firebase_auth_stub = ModuleType('firebase_admin.auth')
    firebase_auth_stub.InvalidIdTokenError = type('InvalidIdTokenError', (Exception,), {})
    firebase_stub = ModuleType('firebase_admin')
    firebase_stub.auth = firebase_auth_stub

    google_pkg = ModuleType('google')
    google_pkg.__path__ = []  # type: ignore[attr-defined]
    google_cloud_pkg = ModuleType('google.cloud')
    google_cloud_pkg.__path__ = []  # type: ignore[attr-defined]
    firestore_stub = ModuleType('google.cloud.firestore')
    firestore_stub.Client = MagicMock
    firestore_stub.ArrayUnion = MagicMock()
    firestore_stub.ArrayRemove = MagicMock()
    firestore_stub.Increment = MagicMock()
    firestore_stub.SERVER_TIMESTAMP = object()
    firestore_stub.DELETE_FIELD = object()
    firestore_stub.FieldFilter = MagicMock()
    firestore_stub.Query = MagicMock()
    google_cloud_pkg.firestore = firestore_stub

    clients_stub = ModuleType('utils.llm.clients')
    clients_stub.embeddings = MagicMock()

    fakes = {
        'pinecone': pinecone_stub,
        'firebase_admin': firebase_stub,
        'firebase_admin.auth': firebase_auth_stub,
        'google': google_pkg,
        'google.cloud': google_cloud_pkg,
        'google.cloud.firestore': firestore_stub,
        'utils.llm.clients': clients_stub,
    }
    return fakes


@pytest.fixture(scope='module')
def vector_db():
    fakes = _load_vector_db_fresh()
    with stub_modules(fakes):
        yield load_module_fresh(
            'local_vector_index_vector_db',
            os.path.join(str(_BACKEND), 'database', 'vector_db.py'),
        )


class TestVectorDbEndToEndWithLocalIndex:
    """Point vector_db.index at a real LocalVectorIndex and exercise public helpers."""

    def test_query_vectors_roundtrip(self, tmp_path, monkeypatch, vector_db):
        from database.local_vector_index import LocalVectorIndex

        local_idx = LocalVectorIndex(path=str(tmp_path / 'v.sqlite3'))
        monkeypatch.setattr(vector_db, 'index', local_idx)

        vector_db.upsert_vector2('u1', 'conv-1', [1.0, 0.0, 0.0, 0.0], {'uid': 'u1'})
        vector_db.upsert_vector2('u1', 'conv-2', [0.9, 0.1, 0.0, 0.0], {'uid': 'u1'})
        vector_db.upsert_vector2('u2', 'conv-9', [1.0, 0.0, 0.0, 0.0], {'uid': 'u2'})

        found = vector_db.query_vectors('anything', 'u1', k=5, query_vector=[1.0, 0.0, 0.0, 0.0])
        assert found == ['conv-1', 'conv-2']

        vector_db.delete_vector('u1', 'conv-1')
        remaining = vector_db.query_vectors('anything', 'u1', k=5, query_vector=[1.0, 0.0, 0.0, 0.0])
        assert remaining == ['conv-2']

    def test_date_filtered_query_vectors_roundtrip(self, tmp_path, monkeypatch, vector_db):
        from database.local_vector_index import LocalVectorIndex

        local_idx = LocalVectorIndex(path=str(tmp_path / 'v.sqlite3'))
        monkeypatch.setattr(vector_db, 'index', local_idx)

        vector_db.upsert_vector2('u1', 'old', [1.0, 0.0], {'uid': 'u1', 'created_at': 100})
        vector_db.upsert_vector2('u1', 'new', [1.0, 0.0], {'uid': 'u1', 'created_at': 500})

        found = vector_db.query_vectors('q', 'u1', starts_at=200, ends_at=600, k=5, query_vector=[1.0, 0.0])
        assert found == ['new']

    def test_persistence_across_instances(self, tmp_path):
        from database.local_vector_index import LocalVectorIndex

        path = str(tmp_path / 'v.sqlite3')
        writer = LocalVectorIndex(path=path)
        writer.upsert(vectors=[{'id': 'a', 'values': _vec(1.0), 'metadata': {'uid': 'u'}}], namespace='ns1')

        reader = LocalVectorIndex(path=path)
        res = reader.query(vector=_vec(1.0), top_k=5, include_metadata=True, namespace='ns1')
        assert [m['id'] for m in res['matches']] == ['a']


class TestLocalBackendWiring:
    def test_local_index_selected_when_env_enabled(self, tmp_path, monkeypatch):
        """LOCAL_VECTOR_ENABLED=true + no pinecone keys -> module-level index is local."""
        monkeypatch.setenv('LOCAL_VECTOR_ENABLED', 'true')
        monkeypatch.setenv('LOCAL_VECTOR_DB_PATH', str(tmp_path / 'v.sqlite3'))
        monkeypatch.delenv('PINECONE_API_KEY', raising=False)
        fakes = _load_vector_db_fresh()
        with stub_modules(fakes):
            mod = load_module_fresh(
                'local_wiring_enabled_vector_db',
                os.path.join(str(_BACKEND), 'database', 'vector_db.py'),
            )
        from database.local_vector_index import LocalVectorIndex

        assert isinstance(mod.index, LocalVectorIndex)

    def test_index_none_when_no_backend_configured(self, tmp_path, monkeypatch):
        """Neither pinecone keys nor LOCAL_VECTOR_ENABLED -> legacy None behaviour."""
        monkeypatch.delenv('LOCAL_VECTOR_ENABLED', raising=False)
        monkeypatch.delenv('PINECONE_API_KEY', raising=False)
        fakes = _load_vector_db_fresh()
        with stub_modules(fakes):
            mod = load_module_fresh(
                'local_wiring_disabled_vector_db',
                os.path.join(str(_BACKEND), 'database', 'vector_db.py'),
            )
        assert mod.index is None
