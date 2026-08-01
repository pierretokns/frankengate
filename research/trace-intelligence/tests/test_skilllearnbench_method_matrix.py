import json

import pytest

from skilllearnbench_method_matrix import build_matrix


def test_method_matrix_requires_complete_same_task_artifacts(tmp_path):
    root = tmp_path / "bench"
    (root / "tasks" / "task-a").mkdir(parents=True)
    (root / "tasks" / "task-b").mkdir()
    for method in (
        "human_authored",
        "b1-one-shot-claude-sonnet-4-6",
        "b2-self-feedback-claude-sonnet-4-6",
        "b3-teacher-feedback-claude-sonnet-4-6",
        "b4-skill-creator-claude-sonnet-4-6",
    ):
        for task in ("task-a", "task-b"):
            (root / "skills" / method / task).mkdir(parents=True)
            (root / "skills" / method / task / "SKILL.md").write_text("# x\n", encoding="utf-8")
    result = build_matrix(root)
    assert result["claim_boundary"]["matrix_ready"] is True
    assert result["design"]["method_count"] == 6
    assert all(row["task_set_sha256"] == result["design"]["task_set_sha256"] for row in result["methods"])
    assert result["methods"][0]["null_baseline"] is True


def test_method_matrix_marks_missing_artifacts(tmp_path):
    root = tmp_path / "bench"
    (root / "tasks" / "task-a").mkdir(parents=True)
    result = build_matrix(root)
    assert result["claim_boundary"]["matrix_ready"] is False
    assert result["missing_task_directories"]["human_authored"] == ["task-a"]
