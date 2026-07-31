import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
RECEIPT = ROOT / "experiments/results/postgres-pitr-lab-2026-08-02.json"


class PostgresPitrReceiptTests(unittest.TestCase):
    def test_local_pitr_and_managed_claims_are_separate(self):
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        boundary = receipt["claim_boundary"]
        pitr = receipt["pitr"]
        self.assertTrue(boundary["local_postgresql_pitr_mechanics_proven"])
        self.assertFalse(boundary["managed_aurora_pitr_proven"])
        self.assertTrue(pitr["executed"])
        self.assertTrue(pitr["target_excluded_after_marker"])
        self.assertEqual(0, pitr["after_marker_rows_at_target"])


if __name__ == "__main__":
    unittest.main()
