from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "matm_embedding_similarity_benchmark",
    ROOT / "matm_embedding_similarity_benchmark.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
try:
    SPEC.loader.exec_module(MODULE)
except ModuleNotFoundError:
    # The benchmark runs in its isolated pyarrow/numpy environment; the core
    # research unit-test environment intentionally has no data-science stack.
    MODULE = None


@unittest.skipIf(MODULE is None, "optional numpy/pyarrow benchmark dependencies are unavailable")
class MatmEmbeddingSimilarityTests(unittest.TestCase):
    def test_work_signature_excludes_model_local_task_id(self) -> None:
        row = {"task_type": "pick_and_place_simple", "goal": "Put some book on sofa.", "task_id": "model-local"}
        self.assertEqual(
            MODULE.work_signature(row),
            "pick_and_place_simple|put some book on sofa.",
        )

    def test_bootstrap_delta_is_reproducible(self) -> None:
        results = {
            "a": {"folds": [{"held_out_model": "m1", "recall_at_k": {"20": 0.8}}, {"held_out_model": "m2", "recall_at_k": {"20": 0.6}}]},
            "b": {"folds": [{"held_out_model": "m1", "recall_at_k": {"20": 0.5}}, {"held_out_model": "m2", "recall_at_k": {"20": 0.5}}]},
        }
        result = MODULE.bootstrap_delta(results, "a", "b", ("recall_at_k", "20"))
        self.assertEqual(result["folds"], 2)
        self.assertAlmostEqual(result["mean_delta"], 0.2)


if __name__ == "__main__":
    unittest.main()
