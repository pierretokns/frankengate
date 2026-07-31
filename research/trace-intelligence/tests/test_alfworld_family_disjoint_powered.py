import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import alfworld_family_disjoint_powered as powered


class FamilyDisjointSelectionTest(unittest.TestCase):
    def test_control_arm_is_registered(self):
        self.assertIn("formatting_placebo", powered.ARMS)

    def test_selection_is_deterministic_and_excludes_prior_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for family in powered.FAMILIES:
                for index in range(3):
                    task = root / f"{family}-fixture" / f"trial-{index}" / "game.tw-pddl"
                    task.parent.mkdir(parents=True)
                    task.write_text("fixture\n", encoding="utf-8")
                    paths.append(str(task))
            excluded = {powered.sha256_text(paths[0])}
            with patch.object(powered, "expert_steps", return_value=(4, True)):
                selected, controls = powered.select_tasks(root, {}, 2, 35, excluded)
            self.assertEqual(len(selected), 8)
            self.assertNotIn(paths[0], selected)
            self.assertEqual(len(controls), 8)
            self.assertTrue(all(row["expert_won"] for row in controls))
            self.assertTrue(all(row["expert_steps"] == 4 for row in controls))


if __name__ == "__main__":
    unittest.main()
