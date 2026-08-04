import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "experiments/results/natural-model-dream-procedure-2026-08-02.json"
VERIFICATION = ROOT / "experiments/results/natural-model-dream-procedure-verification-2026-08-02.json"


class NaturalModelDreamProcedureTest(unittest.TestCase):
    def test_local_model_null_is_verified_without_utility_claim(self):
        result = json.loads(RESULT.read_text(encoding="utf-8"))
        verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))
        self.assertEqual(result["model"], "qwen3:4b")
        self.assertEqual(result["projects_attempted"], 3)
        self.assertEqual(result["projects_quality_passed"], 0)
        self.assertFalse(result["claim_boundary"]["semantic_procedure_quality_confirmed"])
        self.assertFalse(result["claim_boundary"]["causal_skill_or_memory_utility_confirmed"])
        self.assertTrue(verification["all_passed"])
        self.assertFalse(result["content_policy"]["raw_trace_content_emitted"])


if __name__ == "__main__":
    unittest.main()
