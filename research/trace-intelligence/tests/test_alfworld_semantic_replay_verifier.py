import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alfworld_semantic_replay_verifier import task_index  # noqa: E402


class SemanticReplayVerifierTest(unittest.TestCase):
    def test_task_index_is_hash_addressed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "valid_unseen" / "look_at_obj_in_light-fixture" / "trial"
            root.mkdir(parents=True)
            task = root / "game.tw-pddl"
            task.write_text("fixture", encoding="utf-8")
            index = task_index(task.parents[2])
            self.assertEqual(len(index), 1)
            self.assertEqual(next(iter(index.values())), str(task))


if __name__ == "__main__":
    unittest.main()
