import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lrat_trajectory_audit import sha256  # noqa: E402
from verify_lrat_trajectory_audit import verify  # noqa: E402


def test_verify_lrat_hashes_and_claim_boundary(tmp_path: Path) -> None:
    raw = tmp_path / "0.json"
    raw.write_text("{}", encoding="utf-8")
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "schema_version": "frankengate-lrat-trajectory-audit-v1",
                "dataset": {"trajectory_files": 1},
                "records": {"tool_calls": 1, "nonempty_tool_outputs": 1},
                "claim_boundary": {"enterprise_alias_or_artifact_learning_measured": False},
                "raw_receipts": [{"relative_path": "0.json", "sha256": sha256(raw)}],
            }
        ),
        encoding="utf-8",
    )
    assert verify(result, tmp_path)["verification_passed"] is True
