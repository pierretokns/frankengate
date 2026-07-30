import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "defog_terminal_protocol_analysis.py"
)
SPEC = importlib.util.spec_from_file_location(
    "defog_terminal_protocol_analysis",
    MODULE_PATH,
)
analysis = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = analysis
SPEC.loader.exec_module(analysis)


class DefogTerminalProtocolAnalysisTest(unittest.TestCase):
    def test_protocol_repair_and_null_paired_effect_are_separate_gates(self):
        stable = {
            "cohort_manifest_sha256": "a" * 64,
            "dataset_manifest_sha256": "b" * 64,
            "design_manifest_sha256": "c" * 64,
            "model_manifest_sha256": "d" * 64,
            "authority_manifest_sha256": "e" * 64,
        }
        arms = [
            "no_skill",
            "unrelated_formatting_placebo",
            "expert_schema_navigation_seed",
        ]

        def rows(*, repaired):
            values = []
            for task, passed in (("task-1", True), ("task-2", False)):
                for arm in arms:
                    values.append(
                        {
                            "task_id_sha256": task,
                            "arm": arm,
                            "semantic_correct": passed,
                            "policy_accepted": True if passed else None,
                            "unauthorized_observation": False,
                            "terminal_action": (
                                "submit_sql"
                                if repaired or task == "task-1"
                                else "none"
                            ),
                            "protocol_failure_code": None,
                        }
                    )
            return values

        original = {
            "source_receipts": stable,
            "prompt_receipts": {"tool_schema_sha256": "f" * 64},
            "task_receipts": rows(repaired=False),
        }
        repaired = {
            "source_receipts": stable,
            "prompt_receipts": {"tool_schema_sha256": "f" * 64},
            "protocol_remediation": {"id": "terminal-v1"},
            "task_receipts": rows(repaired=True),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            original_path = root / "original.json"
            repaired_path = root / "repaired.json"
            original_path.write_text(json.dumps(original), encoding="utf-8")
            repaired_path.write_text(json.dumps(repaired), encoding="utf-8")
            result = analysis.analyze(
                original_path=original_path,
                repaired_path=repaired_path,
            )

        self.assertTrue(result["contract_invariants"]["all_match"])
        self.assertEqual(
            0.5,
            result["protocol"]["original_failure_rate_by_arm"][
                "expert_schema_navigation_seed"
            ],
        )
        self.assertEqual(
            0.0,
            result["protocol"]["repaired_failure_rate_by_arm"][
                "expert_schema_navigation_seed"
            ],
        )
        self.assertTrue(result["gates"]["terminal_protocol_passed"])
        self.assertFalse(result["gates"]["paired_sensitivity_passed"])
        self.assertFalse(result["gates"]["p1_effect_screen_unsealed"])
        self.assertEqual(
            {"wins": 0, "losses": 0, "ties": 2, "risk_difference": 0.0},
            result["paired_effects"][
                "expert_schema_navigation_seed_vs_"
                "unrelated_formatting_placebo"
            ],
        )


if __name__ == "__main__":
    unittest.main()
