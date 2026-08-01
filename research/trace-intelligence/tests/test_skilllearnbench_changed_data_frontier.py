from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skilllearnbench_changed_data_frontier import prepare_changed_task


def test_prepare_changed_task_renames_prompt_content_and_product_file(tmp_path: Path):
    source = tmp_path / "dataset" / "tasks" / "family" / "task-1"
    (source / "environment" / "DATA" / "products").mkdir(parents=True)
    (source / "environment" / "question.txt").write_text("ContentForce\n")
    (source / "environment" / "DATA" / "products" / "ContentForce.json").write_text(
        '{"name": "ContentForce"}\n'
    )
    (source / "tests").mkdir()
    (source / "tests" / "test_outputs.py").write_text(
        "EXPECTED_ANSWER_Q1 = ['id']\nEXPECTED_ANSWER_Q3 = ['url']\n"
    )
    changed = prepare_changed_task(
        dataset_root=tmp_path / "dataset",
        task_id="family/task-1",
        changed_root=tmp_path / "changed",
        old_name="ContentForce",
        new_name="ContentHub",
    )
    assert (changed / "environment" / "question.txt").read_text() == "ContentHub\n"
    assert not (changed / "environment" / "DATA" / "products" / "ContentForce.json").exists()
    assert (changed / "environment" / "DATA" / "products" / "ContentHub.json").read_text() == '{"name": "ContentHub"}\n'
