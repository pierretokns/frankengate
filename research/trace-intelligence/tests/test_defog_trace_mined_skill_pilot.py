from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from defog_trace_mined_skill_pilot import ARMS, ARM_ADDITIONS, _arm_prompt_addition


class DefogTraceMinedSkillPilotTest(unittest.TestCase):
    def test_pilot_has_baseline_placebo_and_trace_mined_arms(self) -> None:
        self.assertEqual(
            ARMS,
            (
                "no_skill",
                "formatting_placebo",
                "trace_mined_terminal_discipline",
                "trace2skill_compiled_procedure",
            ),
        )
        self.assertEqual(ARM_ADDITIONS["no_skill"], "")
        self.assertNotEqual(
            ARM_ADDITIONS["formatting_placebo"],
            ARM_ADDITIONS["trace_mined_terminal_discipline"],
        )

    def test_length_matched_neutral_is_content_free_and_same_length(self) -> None:
        candidate = "candidate identifier and schema procedure " * 8
        neutral = _arm_prompt_addition("length_matched_neutral", False, candidate)
        self.assertEqual(len(neutral), len(candidate))
        self.assertNotIn("schema", neutral.lower())
        self.assertNotIn("sql", neutral.lower())
