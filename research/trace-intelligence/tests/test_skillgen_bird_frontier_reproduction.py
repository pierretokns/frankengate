from __future__ import annotations

import json
from pathlib import Path


def test_bird_skillgen_has_independent_heldout_rejection() -> None:
    path = Path(__file__).parents[1] / "experiments/results/skillgen-codex-bird-frontier-2026-08-02.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "passed"
    assert data["baseline_failures"] == 6
    assert data["generated_skill"] is True
    held = data["heldout"]
    assert held["n"] == 8
    assert held["baseline_acc"] == 0.5
    assert held["skill_acc"] == 0.375
    assert held["repair"] == 0
    assert held["regression"] == 1
    assert held["net_gain"] == -1
    assert held["passed"] is False


def test_synthetic_sql_cohort_is_not_mislabeled_as_efficacy() -> None:
    path = Path(__file__).parents[1] / "experiments/results/skillgen-codex-sql-frontier-2026-08-02.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "passed"
    assert data["baseline_failures"] == 0
    assert data["generated_skill"] is False
    assert data["heldout"] is None
