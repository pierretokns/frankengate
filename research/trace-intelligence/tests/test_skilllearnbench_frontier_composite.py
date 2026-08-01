from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skilllearnbench_frontier_composite import run_composite, summarize_existing


def test_composite_fails_closed_for_missing_skill_root(tmp_path):
    with pytest.raises(ValueError, match="composite skill root"):
        run_composite(
            dataset_root=tmp_path,
            composite_root=tmp_path / "missing",
            task_ids=["family/task-1"],
            work_root=tmp_path / "work",
            model="test",
            timeout=1,
        )


def test_existing_only_records_unfinished_task_without_launching(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "skilllearnbench_frontier_composite.subprocess.check_output",
        lambda *args, **kwargs: "dataset-revision\n",
    )
    dataset = tmp_path / "dataset"
    task = dataset / "tasks" / "family" / "task-1"
    (task / "tests").mkdir(parents=True)
    (task / "tests" / "test_outputs.py").write_text(
        "EXPECTED_ANSWER_Q1 = ['id-1']\nEXPECTED_ANSWER_Q3 = ['url-1']\n"
    )
    (task / "instruction.md").write_text("answer")
    (task / "environment").mkdir()
    composite = tmp_path / "skills" / "family"
    composite.mkdir(parents=True)
    result = run_composite(
        dataset_root=dataset,
        composite_root=tmp_path / "skills",
        task_ids=["family/task-1"],
        work_root=tmp_path / "work",
        model="test",
        timeout=1,
        existing_only=True,
    )
    assert result["tasks"] == [
        {"task_id": "family/task-1", "arms": [], "status": "not_completed"}
    ]


def test_summarize_existing_marks_missing_answer_as_incomplete(tmp_path, monkeypatch):
    dataset_root = tmp_path / "dataset"
    task_root = dataset_root / "tasks" / "family" / "task-1"
    task_root.mkdir(parents=True)
    (task_root / "expected.json").write_text(
        '{"answer": "ok"}\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        "skilllearnbench_frontier_composite.subprocess.check_output",
        lambda *args, **kwargs: "dataset-revision\n",
    )
    result = summarize_existing(
        dataset_root=dataset_root,
        work_root=tmp_path / "work",
        task_ids=["family/task-1"],
        model="test",
    )
    assert result["execution"] == {
        "completed_tasks": 0,
        "incomplete_tasks": 1,
        "full_paired_run": False,
    }
    assert result["tasks"][0]["status"] == "timeout_or_missing_answer"
