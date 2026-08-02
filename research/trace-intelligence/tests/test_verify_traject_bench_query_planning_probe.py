import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traject_bench_query_planning_probe import sha256  # noqa: E402
from verify_traject_bench_query_planning_probe import verify  # noqa: E402


def test_verify_query_planning_receipt(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = raw_dir / "case-000.json"
    raw.write_text("{}", encoding="utf-8")
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "schema_version": "frankengate-traject-bench-query-planning-probe-v1",
                "dataset": {"selected_cases": 1},
                "failures": 0,
                "protocol": {"planner_sees_gold_targets": False, "planner_sees_tool_outputs": False},
                "raw_receipts": [{"case_index": 0, "raw_sha256": sha256(raw)}],
                "arms": {
                    "baseline": {"records": 1, "candidate_coverage": 0.0, "mrr": 0.0, "recall_at_1": 0.0, "recall_at_5": 0.0, "recall_at_10": 0.0},
                    "planned": {"records": 1, "candidate_coverage": 1.0, "mrr": 1.0, "recall_at_1": 1.0, "recall_at_5": 1.0, "recall_at_10": 1.0},
                },
            }
        ),
        encoding="utf-8",
    )
    assert verify(result, raw_dir)["verification_passed"] is True
