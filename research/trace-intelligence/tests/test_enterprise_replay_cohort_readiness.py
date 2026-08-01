from __future__ import annotations

from enterprise_replay_cohort_readiness import audit
from enterprise_replay_protocol_selftest import build


def test_synthetic_protocol_fixture_passes_all_admission_gates(tmp_path):
    path = tmp_path / "synthetic.json"
    import json

    path.write_text(json.dumps(build()), encoding="utf-8")
    result = audit(path)
    assert result["ready_for_causal_replay"] is True
    assert result["invalid_required_values"] == {}
    assert result["duplicate_task_id_count"] == 0
    assert result["changed_environment_count"] == 2
    assert all(result["minimum_gate"].values())


def test_shape_only_cohort_is_rejected(tmp_path):
    import json

    row = {
        "principal_id": "p1",
        "team_id": "t1",
        "project_id": "project",
        "system_id": "system",
        "effective_time": "2026-01-01",
        "task_id": "duplicate",
        "annotator_a_label": "exact",
        "annotator_b_label": "exact",
        "changed_environment_id": "changed-1",
        "independent_outcome": "verified",
        "negative_kind": None,
    }
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps({"records": [row, {**row, "principal_id": "p2"}]}), encoding="utf-8")
    result = audit(path)
    assert result["ready_for_causal_replay"] is False
    assert result["duplicate_task_id_count"] == 1
    assert result["changed_environment_count"] == 1
    assert result["minimum_gate"]["unique_task_ids"] is False
    assert result["minimum_gate"]["multiple_changed_environments"] is False
