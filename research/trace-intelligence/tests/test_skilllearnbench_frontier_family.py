from __future__ import annotations

import json

from skilllearnbench_frontier_family import run_family


def test_family_rejects_missing_task(tmp_path):
    try:
        run_family(
            dataset_root=tmp_path,
            task_ids=["missing/task-1"],
            arms=["none"],
            work_root=tmp_path / "work",
            model="test",
            timeout=1,
        )
    except ValueError as exc:
        assert "task not found" in str(exc)
    else:
        raise AssertionError("missing task should fail closed")
