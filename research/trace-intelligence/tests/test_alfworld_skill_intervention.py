import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("alfworld_skill_intervention", ROOT / "alfworld_skill_intervention.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AlfworldSkillInterventionTests(unittest.TestCase):
    def test_trace_candidate_is_content_minimized_and_stable(self):
        self.assertIn("successful action templates", MODULE.TRACE_MINED_SKILL)
        self.assertNotIn("Your task is", MODULE.TRACE_MINED_SKILL)

    def test_revised_candidate_is_short_and_action_contract_safe(self):
        self.assertIn("exactly one admissible action", MODULE.TRACE_MINED_SKILL_V2)
        self.assertIn("Re-read the observation", MODULE.TRACE_MINED_SKILL_V2)
        self.assertLess(len(MODULE.TRACE_MINED_SKILL_V2), len(MODULE.TRACE_MINED_SKILL))

    def test_working_memory_candidate_is_explicitly_prior_action_only(self):
        self.assertIn("prior actions only", MODULE.TRACE_MINED_SKILL_V2_MEMORY)
        self.assertIn("never invent state", MODULE.TRACE_MINED_SKILL_V2_MEMORY)

    def test_action_parser_prefers_admissible_tagged_action(self):
        action, valid = MODULE.choose_action("<action>go to drawer 1</action>", ["look", "go to drawer 1"])
        self.assertTrue(valid)
        self.assertEqual(action, "go to drawer 1")

    def test_action_parser_accepts_model_single_tag(self):
        action, valid = MODULE.choose_action("<go to drawer 1>", ["look", "go to drawer 1"])
        self.assertTrue(valid)
        self.assertEqual(action, "go to drawer 1")

    def test_action_parser_fails_closed_to_look(self):
        action, valid = MODULE.choose_action("I cannot decide", ["look", "inventory"])
        self.assertFalse(valid)
        self.assertEqual(action, "look")


if __name__ == "__main__":
    unittest.main()
