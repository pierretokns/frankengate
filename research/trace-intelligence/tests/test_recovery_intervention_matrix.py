import json

import pytest

from recovery_intervention_matrix import build_matrix


def _manifest(rows):
    return {"failures": rows}


def test_matrix_freezes_paired_arms_and_hashes(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            _manifest(
                [
                    {"task_name": "a", "task_checksum": "ca", "task_path": "a", "trajectory": "a.json"},
                    {"task_name": "b", "task_checksum": "cb", "task_path": "b", "trajectory": "b.json"},
                ]
            )
        ),
        encoding="utf-8",
    )
    result = build_matrix(path)
    assert result["design"]["paired"] is True
    assert result["design"]["arm_count"] == 5
    assert result["design"]["task_count"] == 2
    assert len({arm["task_set_sha256"] for arm in result["arms"]}) == 1
    assert result["claim_boundary"]["preflight_only"] is True


def test_matrix_rejects_duplicate_task_identity(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            _manifest(
                [
                    {"task_name": "a", "task_checksum": "ca", "task_path": "a", "trajectory": "a.json"},
                    {"task_name": "a", "task_checksum": "cb", "task_path": "a2", "trajectory": "b.json"},
                ]
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not unique"):
        build_matrix(path)
