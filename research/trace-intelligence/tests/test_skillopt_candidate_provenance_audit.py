import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "experiments/results/skillopt-candidate-provenance-audit-2026-08-02.json"


class SkillOptCandidateProvenanceAuditTest(unittest.TestCase):
    def test_empty_and_real_candidate_rows_are_distinguished(self):
        result = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertTrue(result["all_passed"])
        self.assertTrue(result["claim_boundary"]["r20_r21_empty_candidate_rows_not_skill_quality_evidence"])
        self.assertTrue(result["claim_boundary"]["r22_real_candidate_is_the_corrected_transfer_arm"])
        self.assertFalse(result["claim_boundary"]["causal_skill_benefit_confirmed"])
        self.assertFalse(result["raw_content_policy"]["candidate_text_emitted"])


if __name__ == "__main__":
    unittest.main()
