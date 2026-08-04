import tempfile
import unittest
from pathlib import Path

from bird_interact_ambiguity_profile import profile
from verify_bird_interact_ambiguity_profile import verify


class BirdInteractAmbiguityProfileTest(unittest.TestCase):
    INPUT = Path("/private/tmp/bird-interact-full/bird_interact_data.jsonl")

    @unittest.skipUnless(INPUT.exists(), "pinned BIRD-Interact task file is not present")
    def test_profile_is_content_free_and_partitioned(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            receipt = profile(self.INPUT, receipt_path)
            self.assertEqual(receipt["source"]["records"], 600)
            self.assertEqual(receipt["aggregate"]["records_with_follow_up"], 600)
            self.assertGreater(receipt["aggregate"]["records_with_critical_ambiguity"], 0)
            self.assertEqual(verify(receipt_path)["status"], "verified")


if __name__ == "__main__":
    unittest.main()
