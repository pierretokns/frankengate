import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import postgres_planner_readiness_gate as gate  # noqa: E402


class PlannerReadinessGateTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(
            (ROOT / "configs/experiments/postgres-planner-readiness-v1-2026-08-02.json").read_text()
        )
        self.paired = json.loads(
            (ROOT / "experiments/results/wisp-postgres-planner-statistics-2026-07-30.json").read_text()
        )

    def test_before_fails_and_after_passes(self):
        result = gate.evaluate(self.paired, self.policy)
        self.assertEqual(result["before"]["status"], "not_ready")
        self.assertEqual(result["after"]["status"], "ready")
        self.assertTrue(result["decision"]["release_gate"])
        self.assertTrue(gate.verify_result(result))

    def test_denial_receipt_failure_blocks_readiness(self):
        paired = json.loads(json.dumps(self.paired))
        paired["denied_pre_ranking_candidates_after"] = 1
        result = gate.evaluate(paired, self.policy)
        self.assertEqual(result["after"]["status"], "not_ready")
        self.assertFalse(result["decision"]["release_gate"])


if __name__ == "__main__":
    unittest.main()
