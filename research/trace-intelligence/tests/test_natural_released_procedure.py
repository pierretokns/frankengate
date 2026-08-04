import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
MODULE = ROOT / "natural_released_procedure_verifier.py"
SPEC = importlib.util.spec_from_file_location("natural_released_procedure_verifier", MODULE)
verifier = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(verifier)


class NaturalReleasedProcedureVerifierTest(unittest.TestCase):
    def test_published_receipt_passes_independent_checks(self):
        path = ROOT / "experiments/results/natural-released-procedure-2026-08-02.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        checked = verifier.verify(result)
        self.assertTrue(checked["all_passed"])
        self.assertEqual(3, checked["projects_verified"])
        self.assertEqual(23, checked["queries_verified"])

    def test_utility_claim_cannot_be_promoted_by_receipt_shape(self):
        path = ROOT / "experiments/results/natural-released-procedure-2026-08-02.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        result["claim_boundary"]["procedure_quality_confirmed"] = True
        checked = verifier.verify(result)
        self.assertFalse(checked["all_passed"])


if __name__ == "__main__":
    unittest.main()
