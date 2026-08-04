import importlib.util
import pathlib
import tempfile
import unittest


PATH = pathlib.Path(__file__).parents[1] / "skill_learning_faithful_preflight.py"
SPEC = importlib.util.spec_from_file_location("skill_learning_faithful_preflight", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SkillLearningFaithfulPreflightTest(unittest.TestCase):
    def test_source_contract_detects_the_pinned_validator_mismatch(self):
        root = pathlib.Path("/private/tmp/hermes-self-evolution-pin-research")
        if not root.exists():
            self.skipTest("pinned Hermes self-evolution checkout unavailable")
        facts = MODULE.source_contract(root)
        self.assertTrue(facts["uses_dspy_gepa"])
        self.assertTrue(facts["validator_requires_frontmatter"])
        self.assertTrue(facts["validates_body_without_frontmatter"])
        self.assertTrue(facts["holdout_evaluation_present"])

    def test_missing_mechanism_is_typed(self):
        result = MODULE.build_result(
            hermes_root=None,
            gepa_root=None,
            reasoning_bank_root=None,
            trace2skill_root=None,
        )
        self.assertEqual("unavailable_pinned_source", result["mechanisms"]["gepa_gskill"]["status"])
        self.assertFalse(result["dataset"]["independent_outcome_split_executed"])

    def test_result_does_not_claim_intervention(self):
        result = MODULE.build_result(
            hermes_root=pathlib.Path("/private/tmp/hermes-self-evolution-pin-research"),
            gepa_root=pathlib.Path("/private/tmp/gepa-v0.1.4-research"),
            reasoning_bank_root=None,
            trace2skill_root=pathlib.Path("/private/tmp/trace2skill-3d0b52a-research"),
        )
        self.assertNotEqual("pass", result["mechanisms"]["hermes_self_evolution"]["status"])
        self.assertFalse(result["dataset"]["independent_outcome_split_executed"])


if __name__ == "__main__":
    unittest.main()
