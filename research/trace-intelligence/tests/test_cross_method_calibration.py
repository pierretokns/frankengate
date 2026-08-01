import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("cross_method_calibration", ROOT / "cross_method_calibration.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_paired_power_handles_zero_effect() -> None:
    result = MODULE._paired_power([0.0, 0.0, 0.0])
    assert result["pairs"] == 3
    assert result["observed_mean_delta"] == 0.0
    assert result["estimated_pairs_for_80pct_normal_power"] is None


def test_calibration_reports_measured_and_missing_dimensions() -> None:
    result_dir = ROOT / "experiments" / "results"
    promotion = result_dir / "integration-promotion-audit-2026-08-02.json"
    result = MODULE.calibrate(result_dir, promotion)
    assert result["coverage"]["methods"] == 18
    assert result["coverage"]["paired_effect_measured"] >= 2
    assert result["coverage"]["comparable_cost_measured"] == 0
    assert result["claim_boundary"]["automatic_integration_authorized"] is False
    assert sum(result["null_taxonomy_counts"].values()) == 18


def test_receipt_hashes_are_embedded() -> None:
    result_dir = ROOT / "experiments" / "results"
    promotion = json.loads((result_dir / "integration-promotion-audit-2026-08-02.json").read_text())
    result = MODULE.calibrate(result_dir, result_dir / "integration-promotion-audit-2026-08-02.json")
    by_name = {row["name"]: row for row in result["methods"]}
    for source in promotion["rows"]:
        assert by_name[source["name"]]["receipt_sha256"] == source["receipt_sha256"]
