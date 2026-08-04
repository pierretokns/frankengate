import json
import tempfile
import unittest
from pathlib import Path

from nl2sql_identifier_reranker_benchmark import run
from verify_nl2sql_identifier_reranker_benchmark import verify


class IdentifierRerankerBenchmarkTest(unittest.TestCase):
    RAW = Path("/private/tmp/nl2sql-same-scope-20260803-raw.json")

    @unittest.skipUnless(RAW.exists(), "external collision cohort is not present")
    def test_held_out_ranker_eliminates_collision_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run(self.RAW, Path(directory) / "result.json")
        self.assertEqual(0.0, result["aggregate"]["identifier_reranker"]["same_scope_collision_before_target"])
        self.assertGreater(result["aggregate"]["identifier_reranker"]["recall_at_1"], 0.5)
        self.assertEqual(
            result["aggregate"]["identifier_reranker"],
            result["aggregate"]["hard_negative_reranker"],
        )

    @unittest.skipUnless(RAW.exists(), "external collision cohort is not present")
    def test_verifier_recomputes_content_free_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "result.json"
            result = run(self.RAW, result_path)
            verified = verify(self.RAW, result_path)
        self.assertTrue(verified["verification_passed"])
        self.assertEqual(len(result["per_case"]), verified["cases_verified"])


if __name__ == "__main__":
    unittest.main()
