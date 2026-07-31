import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from alfworld_intervention_receipt_verifier import verify  # noqa: E402


class AlfworldReceiptVerifierTests(unittest.TestCase):
    def test_r3_projection_matches_raw_run(self):
        result = verify(
            ROOT / "experiments/results/alfworld-trace-skill-intervention-r3-2026-08-02.json",
            pathlib.Path("/private/tmp/alfworld-r3-llama-four-families.json"),
        )
        self.assertEqual(result["aggregate_keys_verified"], 4)

    def test_r4_projection_matches_raw_run(self):
        result = verify(
            ROOT / "experiments/results/alfworld-trace-skill-intervention-r4-qwen-2026-08-02.json",
            pathlib.Path("/private/tmp/alfworld-r4-qwen-four-families.json"),
        )
        self.assertEqual(result["aggregate_keys_verified"], 2)


if __name__ == "__main__":
    unittest.main()
