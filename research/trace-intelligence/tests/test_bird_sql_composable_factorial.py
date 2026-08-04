from __future__ import annotations

import json

from bird_sql_composable_factorial import build_library, prompt_for
from bird_sql_composable_factorial_aggregate import run as aggregate_replays


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


def test_aggregate_replays_requires_same_library(tmp_path):
    base = {
        "protocol": {"task_count": 1, "library_sha256": "same", "arms": ["no_skill", "formatting_placebo", "composable_subplan_library"]},
        "episodes": [
            {"task_hash": "task", "arm": "no_skill", "exact": False, "outcome": "mismatch"},
            {"task_hash": "task", "arm": "formatting_placebo", "exact": False, "outcome": "mismatch"},
            {"task_hash": "task", "arm": "composable_subplan_library", "exact": True, "outcome": "exact"},
        ],
    }
    first = tmp_path / "first.json"; second = tmp_path / "second.json"
    verify = tmp_path / "verify.json"; out = tmp_path / "out.json"
    first.write_text(json.dumps(base)); second.write_text(json.dumps(base)); verify.write_text(json.dumps({"claim_boundary": {"verification_passed": True}}))
    result = aggregate_replays((first, second), (verify, verify), out)
    assert result["stable_comparisons"]["no_skill"]["stable_library_wins"] == 1
