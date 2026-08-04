import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
RECEIPT = ROOT / "experiments/results/rho-frontier-locomo-bounded-2026-08-02.json"


class RHOFrontierReproductionTests(unittest.TestCase):
    def test_matched_heldout_control_rejects_self_preference_candidate(self):
        result = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(
            "frankengate-rho-frontier-reproduction-v1", result["schema_version"]
        )
        self.assertTrue(result["protocol"]["candidate_accepted_by_self_preference"])
        self.assertTrue(result["claim_boundary"]["independent_heldout_replay"])
        self.assertTrue(result["claim_boundary"]["matched_no_harness_control"])
        self.assertAlmostEqual(0.7027777777777777, result["outcome"]["baseline_mean_score"])
        self.assertAlmostEqual(0.5111111111111112, result["outcome"]["candidate_mean_score"])
        self.assertAlmostEqual(-0.19166666666666654, result["outcome"]["mean_delta"])
        self.assertEqual(1, result["outcome"]["candidate_regressed_tasks"])
        self.assertFalse(result["claim_boundary"]["causal_rho_utility_confirmed"])
        self.assertFalse(result["claim_boundary"]["automatic_frankengate_promotion_authorized"])


if __name__ == "__main__":
    unittest.main()
