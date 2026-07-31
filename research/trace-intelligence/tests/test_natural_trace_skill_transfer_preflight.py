from __future__ import annotations

import json
from pathlib import Path

from natural_trace_skill_transfer_preflight import run


def test_preflight_keeps_historical_matrix_distinct_from_causal_skill_claim(tmp_path: Path) -> None:
    manifest = {
        "bounded_tasks": ["t1"],
        "protocol": {"source_arms": ["claude-code__opus-4.7"]},
        "dataset": {"id": "fixture", "revision": "r1"},
        "raw_trace_policy": "external",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir()
    (results / "claude-code-opus-4.7__t1.json").write_text(
        json.dumps({"status": "success", "model": "opus"}), encoding="utf-8"
    )

    receipt = run(manifest_path, results)

    assert receipt["observed_result_count"] == 1
    assert receipt["missing_result_count"] == 0
    assert receipt["claim_boundary"]["historical_outcome_matrix_available"] is True
    assert receipt["claim_boundary"]["natural_trace_skill_benefit_confirmed"] is False
    assert receipt["claim_boundary"]["causal_intervention_run"] is False


def test_preflight_reports_missing_arms(tmp_path: Path) -> None:
    manifest = {
        "bounded_tasks": ["t1"],
        "protocol": {"source_arms": ["a", "b"]},
        "dataset": {"id": "fixture", "revision": "r1"},
        "raw_trace_policy": "external",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir()
    (results / "a__t1.json").write_text(json.dumps({"status": "timeout"}), encoding="utf-8")

    receipt = run(manifest_path, results)

    assert receipt["observed_result_count"] == 1
    assert receipt["missing_result_count"] == 1
    assert receipt["claim_boundary"]["historical_outcome_matrix_available"] is False
