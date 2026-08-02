from __future__ import annotations

import json

from bird_sql_composable_factorial import build_library, prompt_for


def test_library_uses_only_source_families(tmp_path):
    tasks = [
        {"task_id": "source-1", "prompt": "source question", "data": {"db_name": "source"}},
        {"task_id": "target-1", "prompt": "target question", "data": {"db_name": "target"}},
    ]
    (tmp_path / "source-1.json").write_text(json.dumps({"gold_sql": "SELECT 1"}))
    library = build_library(tasks, gold_dir=tmp_path, source_families=["source"], per_family=1)
    assert "source question" in library
    assert "target question" not in library
    assert "SELECT 1" in library


def test_composable_prompt_preserves_target_and_library_boundary():
    prompt = prompt_for(
        {"prompt": "target question"},
        "CREATE TABLE target (id INTEGER);",
        "composable_subplan_library",
        "EXAMPLE 1\nValidated SQL: SELECT 1",
    )
    assert "target question" in prompt
    assert "CREATE TABLE target" in prompt
    assert "Validated SQL: SELECT 1" in prompt
    assert "do not copy a whole source query" in prompt.lower()

