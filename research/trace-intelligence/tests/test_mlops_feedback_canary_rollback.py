from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mlops_feedback_loop_canary_rollback",
    ROOT / "mlops_feedback_loop_canary_rollback.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MLOpsCanaryRollbackTests(unittest.TestCase):
    def test_positive_release_then_regression_rolls_back(self) -> None:
        result = MODULE.run()
        self.assertTrue(result["release"]["passed"])
        self.assertTrue(result["monitor"]["windows"][0]["healthy"])
        self.assertFalse(result["monitor"]["windows"][1]["healthy"])
        self.assertTrue(result["rollback"]["triggered"])
        self.assertTrue(result["rollback"]["restored_previous"])
        self.assertEqual(result["rollback"]["canary_percent_after"], 0)
        self.assertFalse(result["claim_boundary"]["causal_model_utility_confirmed"])


if __name__ == "__main__":
    unittest.main()
