import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bird_artifact_query_planning_probe import sha256  # noqa: E402
from verify_bird_artifact_query_planning_probe import verify  # noqa: E402


def test_verify_bird_query_planning_receipt(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = raw_dir / "case-000.json"
    raw.write_text("{}", encoding="utf-8")
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "schema_version": "frankengate-bird-artifact-query-planning-probe-v1",
                "cohort": {"targets": 1},
                "failures": 0,
                "protocol": {"planner_sees_result_labels": False, "planner_sees_target_sql": False},
                "raw_receipts": [{"case_index": 0, "raw_sha256": sha256(raw)}],
                "rows": [{}],
                "arms": {
                    "baseline": {"targets": 1, "result_match_at_1": 0, "result_match_at_5": 0, "result_match_at_10": 0},
                    "planned": {"targets": 1, "result_match_at_1": 1, "result_match_at_5": 1, "result_match_at_10": 1},
                },
            }
        ),
        encoding="utf-8",
    )
    assert verify(result, raw_dir)["verification_passed"] is True
