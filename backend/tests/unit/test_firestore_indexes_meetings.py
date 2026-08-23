"""Guard for the users/{uid}/meetings overlap composite index.

`calendar_meetings.get_meetings_in_time_range` runs
`start_time < end AND end_time > start ORDER BY start_time`, which Firestore can
only serve with a composite index on (start_time ASC, end_time ASC). Missing it
crashes desktop listen conversation creation with FailedPrecondition
(routers/listen/conversations.py). See docs/superpowers/plans/
2026-08-25-omi-selfhost-docs-parity.md Task 1.
"""

import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[3] / 'firestore.indexes.json'


def _meetings_indexes() -> list[dict]:
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    return [i for i in data.get('indexes', []) if i.get('collectionGroup') == 'meetings']


def test_meetings_overlap_composite_declared():
    fields = {('start_time', 'ASCENDING'), ('end_time', 'ASCENDING')}
    assert any(
        fields.issubset({(f['fieldPath'], f.get('order')) for f in idx.get('fields', [])})
        for idx in _meetings_indexes()
    ), 'meetings (start_time,end_time) composite missing -> routers/listen/conversations.py:257 crash'


def test_meetings_overlap_index_matches_registry_order():
    # The registry declares the canonical shape; the manifest must carry it verbatim.
    expected = [
        {'fieldPath': 'start_time', 'order': 'ASCENDING'},
        {'fieldPath': 'end_time', 'order': 'ASCENDING'},
        {'fieldPath': '__name__', 'order': 'ASCENDING'},
    ]
    assert any(idx.get('fields') == expected for idx in _meetings_indexes()), (
        f'expected meetings index {_expected_message(expected)}, '
        f'got {[idx.get("fields") for idx in _meetings_indexes()]}'
    )


def _expected_message(expected: list[dict]) -> str:
    return ', '.join(f"{f['fieldPath']}:{f['order']}" for f in expected)
