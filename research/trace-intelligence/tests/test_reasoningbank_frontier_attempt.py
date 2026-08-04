import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
RECEIPT = ROOT / "experiments/results/reasoningbank-locomo-bounded-2026-08-02.json"


class ReasoningBankFrontierAttemptTests(unittest.TestCase):
    def test_provider_failure_is_typed_and_not_quality_evidence(self):
        result = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual("unavailable_typed", result["status"])
        self.assertEqual("provider_unavailable", result["claim_boundary"]["classification"])
        self.assertFalse(result["claim_boundary"]["memory_quality_evaluated"])
        self.assertFalse(result["claim_boundary"]["utility_evaluated"])
        self.assertEqual("FileNotFoundError", result["failure"]["exception"])


if __name__ == "__main__":
    unittest.main()
