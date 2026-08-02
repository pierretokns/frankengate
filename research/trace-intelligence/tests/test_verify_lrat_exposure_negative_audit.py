import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_lrat_exposure_negative_audit import verify  # noqa: E402


def test_verify_exposure_receipt(tmp_path: Path) -> None:
    result = {
        "schema_version": "frankengate-lrat-exposure-negative-audit-v1",
        "aggregate": {"trajectories": 1, "search_calls": 1, "browse_calls": 1, "exposed_documents": 2, "browsed_documents": 1, "exposed_unbrowsed_documents": 1, "exposed_unbrowsed_fraction": 0.5},
        "rows": [{}],
        "claim_boundary": {"negative_labels_established": False, "correctness_established": False},
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    assert verify(path)["verification_passed"] is True
