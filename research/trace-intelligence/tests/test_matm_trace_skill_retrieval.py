from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matm_trace_skill_retrieval as retrieval  # noqa: E402


def row(model: str, goal: str, actions: list[str], success: bool) -> dict:
    import json

    return {
        "model": model,
        "goal": goal,
        "task_type": "toy",
        "success": success,
        "trajectory": json.dumps([{"action": action} for action in actions]),
    }


class MatmTraceSkillRetrievalTests(unittest.TestCase):
    def test_normalized_similarity_removes_object_numbers(self):
        left = retrieval._row_features(row("a", "pick the red apple", ["take apple 1"], True))
        right = retrieval._row_features(row("b", "pick the red apple", ["take apple 9"], False))
        self.assertEqual(1.0, retrieval._similarity(left, right))

    def test_model_fold_is_holdout_only_and_content_free(self):
        rows = [
            row("train", "pick apple", ["go apple 1", "take apple 1"], True),
            row("train", "pick apple", ["go apple 2", "take apple 2"], False),
            row("test", "pick apple", ["go apple 8", "take apple 8"], True),
        ]
        result = retrieval._model_fold(rows, "test", 1)
        self.assertEqual(2, result["train_rows"])
        self.assertEqual(1, result["test_rows"])
        self.assertNotIn("goal", str(result))
        self.assertNotIn("trajectory", str(result))

    def test_bootstrap_is_deterministic(self):
        values = [0.1, 0.2, 0.4, 0.7]
        self.assertEqual(
            retrieval._bootstrap_ci(values),
            retrieval._bootstrap_ci(values),
        )


if __name__ == "__main__":
    unittest.main()
