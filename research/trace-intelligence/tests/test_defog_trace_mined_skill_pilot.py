from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from defog_trace_mined_skill_pilot import ARMS, ARM_ADDITIONS


class DefogTraceMinedSkillPilotTest(unittest.TestCase):
    def test_pilot_has_baseline_placebo_and_trace_mined_arms(self) -> None:
        self.assertEqual(
            ARMS,
            ("no_skill", "formatting_placebo", "trace_mined_terminal_discipline"),
        )
        self.assertEqual(ARM_ADDITIONS["no_skill"], "")
        self.assertNotEqual(
            ARM_ADDITIONS["formatting_placebo"],
            ARM_ADDITIONS["trace_mined_terminal_discipline"],
        )
