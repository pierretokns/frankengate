from __future__ import annotations

from artifact_subplan_changed_system_stress import run


def test_stress_grid_preserves_semantic_admission_safety(tmp_path):
    receipt = tmp_path / "receipt.json"
    result = run(receipt, repeats=20)
    assert result["source"]["target_count"] == 100
    assert result["aggregate"]["name_only_subplan"] == {
        "accepted": 100,
        "semantic_correct": 60,
        "unsafe_accept": 40,
        "rejected": 0,
    }
    assert result["aggregate"]["semantic_subplan"] == {
        "accepted": 60,
        "semantic_correct": 60,
        "unsafe_accept": 0,
        "rejected": 40,
    }
