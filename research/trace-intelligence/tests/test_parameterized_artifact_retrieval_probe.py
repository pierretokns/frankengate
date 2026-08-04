import json
import tempfile
import unittest
from pathlib import Path

from parameterized_artifact_retrieval_probe import run
from verify_parameterized_artifact_retrieval_probe import verify


class ParameterizedArtifactRetrievalProbeTest(unittest.TestCase):
    BASIC = Path("/private/tmp/defog-sql-eval-research/data/instruct_basic_postgres.csv")
    ADVANCED = Path("/private/tmp/defog-sql-eval-research/data/instruct_advanced_postgres.csv")
    TARGETS = Path("/private/tmp/defog-sql-eval-research/data/questions_gen_postgres.csv")

    @unittest.skipUnless(BASIC.exists() and ADVANCED.exists() and TARGETS.exists(), "external Defog CSVs are not present")
    def test_parameterized_templates_add_nil_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            result = run(self.BASIC, self.ADVANCED, self.TARGETS, {"broker", "car_dealership"}, receipt_path)
            self.assertEqual(result["aggregate"]["template_gate"]["false_accept_nil"], 0)
            self.assertEqual(result["aggregate"]["lexical"]["false_accept_nil"], result["source"]["template_nil_count"])
            self.assertEqual(result["aggregate"]["template_gate"]["top1_correct"], result["source"]["parameter_mutation_count"])
            self.assertEqual(verify(receipt_path)["status"], "verified")
            payload = json.loads(receipt_path.read_text())
            self.assertFalse(any("question" in row for row in payload["rows"]))


if __name__ == "__main__":
    unittest.main()
