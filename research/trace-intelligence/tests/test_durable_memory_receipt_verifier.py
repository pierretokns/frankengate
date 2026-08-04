import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from durable_memory_receipt_verifier import verify  # noqa: E402


class DurableMemoryReceiptTests(unittest.TestCase):
    def test_r7_matches_external_raw_summary(self):
        result = verify(
            ROOT / "experiments/results/alfworld-durable-memory-intervention-r7-2026-08-02.json",
            pathlib.Path("/private/tmp/alfworld-r7b-durable-memory-llama.json"),
        )
        self.assertEqual(result["summary_keys_verified"], 4)


if __name__ == "__main__":
    unittest.main()
