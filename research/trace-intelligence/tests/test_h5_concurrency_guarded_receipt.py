import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "experiments/results/h5-concurrency-guarded-rerun-2026-08-02.json"


class H5ConcurrencyGuardedReceiptTest(unittest.TestCase):
    def test_receipt_is_content_free_and_fail_closed(self):
        result = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertTrue(result["all_passed"])
        self.assertTrue(result["checks"]["governed_repeatable_read_rejected"])
        self.assertTrue(result["checks"]["invariant_match_to_prior"])
        self.assertEqual(result["live_summary"]["governed_isolation"], "read committed")
        self.assertFalse(result["content_policy"]["raw_live_result_embedded"])
        self.assertFalse(result["content_policy"]["raw_trace_content_emitted"])


if __name__ == "__main__":
    unittest.main()
