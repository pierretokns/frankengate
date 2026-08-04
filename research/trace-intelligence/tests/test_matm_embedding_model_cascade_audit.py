import json
import tempfile
import unittest
from pathlib import Path

from matm_embedding_model_cascade_audit import run


class MATMCascadeAuditTest(unittest.TestCase):
    def test_same_revision_and_non_pooled_decision(self):
        dense = {
            "dataset": {"id": "matm", "revision": "r", "rows": 2},
            "results": {"actions": {"eligible_models": 1, "eligible_queries": 2}},
            "comparisons": [{"left": "actions", "right": "lexical_actions", "metric": "recall_at_k.20", "mean_delta": 0.1, "bootstrap_ci95": [0.0, 0.2], "folds": 1}],
        }
        outcome = {
            "dataset": {"id": "matm", "revision": "r", "rows": 2},
            "aggregate": {"all_trace_neighbor": {"auc": 0.5}, "successful_trace_neighbor": {"auc": 0.5}, "contrast": {}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dense_path, outcome_path = root / "dense.json", root / "outcome.json"
            dense_path.write_text(json.dumps(dense), encoding="utf-8")
            outcome_path.write_text(json.dumps(outcome), encoding="utf-8")
            result = run(dense_path, outcome_path)
        self.assertEqual(result["dataset"]["id"], "matm")
        self.assertFalse(result["decision"]["pooled_metric_claim"])
        self.assertFalse(result["decision"]["skill_release_authorized"])


if __name__ == "__main__":
    unittest.main()
