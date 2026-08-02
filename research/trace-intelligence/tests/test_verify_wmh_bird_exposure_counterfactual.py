from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_wmh_bird_exposure_counterfactual import verify  # noqa: E402


def test_verify_counterfactual_receipt(tmp_path) -> None:
    result = {
        "schema_version": "frankengate-wmh-bird-exposure-counterfactual-v1",
        "aggregate": {
            "selected_successful_tasks": 1,
            "database_families": 1,
            "counterfactual_pairs": 3,
            "counterfactual_execution_errors": 2,
            "counterfactual_result_mismatches": 1,
            "counterfactual_result_matches": 0,
        },
        "rows": [{"counterfactual_error": 2, "counterfactual_mismatch": 1, "counterfactual_match": 0}],
        "retrieval": {"arms": {
            "lexical": {"cases": 1, "mrr": 1.0, "recall_at_1": 1.0, "recall_at_5": 1.0, "recall_at_10": 1.0},
            "lexical_plus_termhood_alias": {"cases": 1, "mrr": 1.0, "recall_at_1": 1.0, "recall_at_5": 1.0, "recall_at_10": 1.0},
        }},
        "claim_boundary": {
            "counterfactual_interchangeability_negatives_measured": True,
            "semantic_negative_labels_established": False,
            "enterprise_alias_quality_established": False,
        },
    }
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    assert verify(path)["verification_passed"] is True
