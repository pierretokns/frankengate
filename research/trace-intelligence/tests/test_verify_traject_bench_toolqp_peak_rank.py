import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_traject_bench_toolqp_peak_rank import verify  # noqa: E402


def test_verify_peak_rank_receipt(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = raw_dir / "case-000.json"
    raw.write_text("{}", encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(b"{}").hexdigest()
    result = tmp_path / "result.json"
    arms = {arm: {"records": 1, "candidate_coverage": 0.0, "mrr": 0.0, "recall_at_1": 0.0, "recall_at_5": 0.0, "recall_at_10": 0.0} for arm in ("baseline", "union", "peak_rank")}
    result.write_text(json.dumps({"schema_version": "frankengate-traject-bench-toolqp-peak-rank-v1", "dataset": {"selected_cases": 1}, "protocol": {"planner_sees_gold_targets": False, "planner_sees_tool_outputs": False, "planner_training_reproduced": False}, "raw_receipts": [{"case_index": 0, "raw_sha256": digest}], "arms": arms}), encoding="utf-8")
    assert verify(result, raw_dir)["verification_passed"] is True
