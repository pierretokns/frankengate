import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_gap_labeled_sweep import run_sweep


def test_labeled_sweep_is_stable():
    result = run_sweep([1, 3])
    assert [row["per_stratum"] for row in result["sizes"]] == [1, 3]
    assert all(row["precision"] == 1.0 for row in result["sizes"])
    assert all(row["recall"] == 1.0 for row in result["sizes"])
