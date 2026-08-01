import json
import tempfile
import unittest
from pathlib import Path

from artifact_changed_system_replay import run
from verify_artifact_changed_system_replay import verify


class ArtifactChangedSystemReplayTest(unittest.TestCase):
    def test_semantic_compatibility_accepts_approved_rename_only(self):
        result = run()
        cases = {case["case_id"]: case for case in result["cases"]}
        self.assertTrue(cases["approved_semantic_rename"]["policies"]["semantic_compatibility"]["accepted"])
        self.assertFalse(cases["semantic_collision"]["policies"]["semantic_compatibility"]["accepted"])
        self.assertFalse(cases["same_name_semantic_drift"]["policies"]["semantic_compatibility"]["accepted"])
        self.assertEqual(0, result["aggregate"]["semantic_compatibility_false_semantic_accepts"])
        self.assertEqual(2, result["aggregate"]["name_compatibility_false_semantic_accepts"])

    def test_receipt_verifier_recomputes_recorded_matrix(self):
        result = run()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
            verified = verify(path)
        self.assertTrue(verified["verification_passed"])
        self.assertEqual(5, verified["cases_verified"])


if __name__ == "__main__":
    unittest.main()
