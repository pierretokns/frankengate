from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "rho_powered_receipt.py"
SPEC = importlib.util.spec_from_file_location("rho_powered_receipt", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_receipt = MODULE.build_receipt
exact_sign_pvalue = MODULE.exact_sign_pvalue


def _run(tmp_path: Path, name: str, rows: list[dict[str, object]]) -> Path:
    run = tmp_path / name / "reports"
    run.mkdir(parents=True)
    (run / "final_val_grades.json").write_text(json.dumps(rows), encoding="utf-8")
    return run.parent


def test_powered_receipt_pairs_tasks_and_reports_interval(tmp_path: Path) -> None:
    candidate = _run(
        tmp_path,
        "candidate",
        [{"task_id": "b", "score": 1.0}, {"task_id": "a", "score": 0.25}],
    )
    baseline = _run(
        tmp_path,
        "baseline",
        [{"task_id": "a", "score": 0.5}, {"task_id": "b", "score": 0.5}],
    )
    dataset = tmp_path / "dataset.json"
    dataset.write_text("[]", encoding="utf-8")

    receipt = build_receipt(candidate, baseline, upstream_commit="abc", dataset=dataset)

    assert receipt["outcome"]["mean_delta"] == 0.125
    assert receipt["outcome"]["candidate_better_tasks"] == 1
    assert receipt["outcome"]["candidate_regressed_tasks"] == 1
    assert len(receipt["outcome"]["bootstrap_mean_delta_95ci"]) == 2
    assert receipt["claim_boundary"]["automatic_frankengate_promotion_authorized"] is False


def test_exact_sign_pvalue_handles_ties() -> None:
    assert exact_sign_pvalue([0.0, 0.0]) == 1.0
    assert exact_sign_pvalue([1.0, 1.0, -1.0]) == 1.0
