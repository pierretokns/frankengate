import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alfworld_powered_receipt_verifier import verify  # noqa: E402


class PoweredReceiptVerifierTest(unittest.TestCase):
    def test_verifies_committed_powered_receipts_against_external_aggregates(self):
        root = Path(__file__).resolve().parents[1]
        cases = [
            ("alfworld-family-disjoint-powered-r9-2026-08-02.json", "/private/tmp/alfworld-family-disjoint-powered-r9.raw.json", 32),
            ("alfworld-family-disjoint-powered-r11-openai-llama-2026-08-02.json", "/private/tmp/alfworld-family-disjoint-powered-r11-openai-llama.raw.json", 16),
        ]
        for receipt_name, raw_name, expected_rows in cases:
            receipt = root / "experiments/results" / receipt_name
            raw = Path(raw_name)
            if not raw.exists():
                self.skipTest(f"external raw receipt is not present: {raw}")
            result = verify(receipt, raw)
            self.assertTrue(result["all_passed"])
            self.assertEqual(result["task_count_verified"], 8)
            self.assertEqual(result["rows_verified"], expected_rows)


if __name__ == "__main__":
    unittest.main()
