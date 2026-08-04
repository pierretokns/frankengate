import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]


class AlfworldInterventionReceiptTests(unittest.TestCase):
    def test_receipt_preserves_negative_claim_boundary(self):
        receipt = json.loads(
            (ROOT / "experiments/results/alfworld-trace-skill-intervention-2026-08-02.json").read_text()
        )
        self.assertEqual(receipt["environment_gate"]["expert_wins"], 2)
        self.assertEqual(receipt["coverage"]["episodes"], 18)
        self.assertEqual(receipt["claim_boundary"]["causal_skill_benefit_confirmed"], False)
        self.assertEqual(receipt["claim_boundary"]["automatic_promotion_authorized"], False)
        self.assertEqual(
            sum(value["wins"] for key, value in receipt["aggregate"].items() if key.endswith("|trace_mined_procedure")),
            0,
        )


if __name__ == "__main__":
    unittest.main()
