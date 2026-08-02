import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_traject_bench_field_retrieval import verify  # noqa: E402


def test_verify_field_retrieval_receipt(tmp_path: Path) -> None:
    result = {
        "schema_version": "frankengate-traject-bench-field-retrieval-v1",
        "records_evaluated": 4,
        "source": {"raw_content_committed": False},
        "claim_boundary": {"embedding_measured": False, "enterprise_quality_measured": False},
        "aggregates": {
            f"domain/hard/{arm}": {
                "records": 1,
                "mrr": 0.5,
                "recall_at_1": 0.5,
                "recall_at_5": 1.0,
                "recall_at_10": 1.0,
                "exact_target_set_at_target_count": 0.0,
            }
            for arm in ("name", "name_description", "field_aware", "identifier_schema")
        },
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    receipt = verify(path)
    assert receipt["verification_passed"] is True
