import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alfworld_powered_receipt_verifier import verify  # noqa: E402


class PoweredReceiptVerifierTest(unittest.TestCase):
    def test_verifies_committed_r9_receipt_against_external_aggregate(self):
        root = Path(__file__).resolve().parents[1]
        receipt = root / "experiments/results/alfworld-family-disjoint-powered-r9-2026-08-02.json"
        raw = Path("/private/tmp/alfworld-family-disjoint-powered-r9.raw.json")
        if not raw.exists():
            self.skipTest("external raw receipt is not present in this environment")
        result = verify(receipt, raw)
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["task_count_verified"], 8)
        self.assertEqual(result["rows_verified"], 32)


if __name__ == "__main__":
    unittest.main()
