import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_wmh_bird_schema_exposure_audit import verify  # noqa: E402


def test_verify_schema_exposure_receipt(tmp_path: Path) -> None:
    result = {"schema_version": "frankengate-wmh-bird-schema-exposure-audit-v1", "aggregate": {"traces": 1, "schema_table_exposures": 2, "consumed_table_identifiers": 1, "exposed_unconsumed_table_identifiers": 1, "exposed_unconsumed_fraction": 0.5, "traces_with_exposed_unconsumed_tables": 1}, "rows": [{}], "claim_boundary": {"semantic_negative_labels_established": False, "validated_artifact_utility_measured": False}}
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    assert verify(path)["verification_passed"] is True
