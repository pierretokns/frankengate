import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
RECEIPT = ROOT / "experiments/results/reasoningbank-codex-frontier-bounded-2026-08-02.json"


class ReasoningBankCodexFrontierTests(unittest.TestCase):
    def test_independent_control_rejects_memory_arm(self):
        result = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertTrue(result["claim_boundary"]["upstream_runner_unchanged"])
        self.assertTrue(result["claim_boundary"]["independent_heldout_replay"])
        self.assertTrue(result["claim_boundary"]["codex_provider_substitution_explicit"])
        self.assertAlmostEqual(0.7027777777777777, result["outcome"]["baseline_mean_score"])
        self.assertAlmostEqual(0.5930555555555557, result["outcome"]["reasoningbank_mean_score"])
        self.assertAlmostEqual(-0.10972222222222205, result["outcome"]["mean_delta"])
        self.assertEqual(1, result["outcome"]["candidate_regressed_tasks"])
        self.assertFalse(result["claim_boundary"]["causal_memory_utility_confirmed"])


if __name__ == "__main__":
    unittest.main()
