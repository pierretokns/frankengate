from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_wmh_bird_replay_negative_reranker import verify  # noqa: E402


def test_verify_reranker_receipt(tmp_path) -> None:
    arms = {name: {"cases": 1, "mrr": 1.0, "recall_at_1": 1.0, "recall_at_5": 1.0, "recall_at_10": 1.0} for name in ("lexical", "termhood_alias", "naive_exposed_negative_ranker", "replay_negative_ranker")}
    result = {"schema_version": "frankengate-wmh-bird-replay-negative-reranker-v1", "arms": arms, "folds": [{"train_tasks": 1, "evaluation_tasks": 1}], "claim_boundary": {"replay_negative_training_evaluated": True, "semantic_negative_labels_established": False, "enterprise_quality_established": False}}
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    assert verify(path)["verification_passed"] is True
