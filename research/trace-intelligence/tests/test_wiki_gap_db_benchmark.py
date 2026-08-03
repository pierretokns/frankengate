import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_gap_db_benchmark import fixture_rows, summarize_times


def test_governed_fixture_rows_are_deterministic_and_scale_linearly():
    root = Path(__file__).resolve().parents[1] / "fixtures" / "governed-v1"
    first = fixture_rows(root, 2)
    second = fixture_rows(root, 2)
    assert first == second
    assert len(first) == 38
    assert len(fixture_rows(root, 3)) == 57


def test_timing_summary_is_stable_for_replay_receipts():
    summary = summarize_times([0.4, 0.2, 0.3, 0.5, 0.1])
    assert summary["runs"] == 5
    assert summary["p50_seconds"] == 0.3
    assert summary["p95_seconds"] == 0.5
