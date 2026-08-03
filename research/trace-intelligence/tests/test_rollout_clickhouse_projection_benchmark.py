import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rollout_clickhouse_projection_benchmark import event_rows, semantic_row
from rollout_ingestion_experiment import build_cohort


def test_delivery_replays_keep_source_version_stable():
    events, _, _ = build_cohort()
    rows = event_rows(events, 4)
    assert len(rows) == len(events) * 4
    assert {row[-1] for row in rows} == {1}
    assert len({row[0] for row in rows}) == len(events)


def test_semantic_projection_ignores_delivery_only_fields():
    events, _, _ = build_cohort()
    first = semantic_row(events[0])
    changed = dict(events[0])
    changed["timestamp"] = "a different delivery timestamp"
    assert semantic_row(changed) == first
