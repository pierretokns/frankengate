import tempfile
import unittest
from pathlib import Path

from bird_interact_sample_audit import audit
from verify_bird_interact_sample_audit import verify


class BirdInteractSampleAuditTest(unittest.TestCase):
    A_MODE = Path("/private/tmp/bird-interact-repo/BIRD-Interact-ADK/examples/a_interact_samples.json")
    C_MODE = Path("/private/tmp/bird-interact-repo/BIRD-Interact-ADK/examples/c_interact_samples.json")

    @unittest.skipUnless(A_MODE.exists() and C_MODE.exists(), "public ADK samples are not present")
    def test_sample_receipt_is_partitioned(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            receipt = audit([self.A_MODE, self.C_MODE], receipt_path)
            self.assertEqual(receipt["aggregate"]["samples"], 20)
            self.assertEqual(set(receipt["aggregate"]["modes"]), {"a-interact", "c-interact"})
            self.assertEqual(verify(receipt_path)["status"], "verified")


if __name__ == "__main__":
    unittest.main()
