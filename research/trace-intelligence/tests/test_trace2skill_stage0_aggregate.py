import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
for name in ("governed_tool_sandbox", "trace2skill_stage0_aggregate"):
    path = ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)

aggregate = sys.modules["trace2skill_stage0_aggregate"]


class Trace2SkillStage0AggregateTest(unittest.TestCase):
    def make_arm(self, root: pathlib.Path, before_pass: bool):
        (root / "audit").mkdir(parents=True)
        (root / "results.json").write_text(
            json.dumps(
                {
                    "successful_instances": 1,
                    "results": [{"test_cases": [{"turns": 3}]}],
                }
            ),
            encoding="utf-8",
        )
        (root / "eval.json").write_text(
            json.dumps(
                {
                    "summary": {
                        "total_instances": 1,
                        "fully_correct_instances": int(before_pass),
                    }
                }
            ),
            encoding="utf-8",
        )
        (root / "audit" / "task.jsonl").write_text(
            json.dumps(
                {
                    "command": "private raw command",
                    "stdout": "Failed to establish a new connection",
                    "stderr": "",
                    "exit_code": 1,
                    "timed_out": False,
                    "sandbox_violation": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_aggregate_counts_harms_without_copying_raw_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "arm"
            self.make_arm(root, before_pass=False)
            post = pathlib.Path(temp) / "post.json"
            post.write_text(
                json.dumps(
                    {
                        "summary": {
                            "total_instances": 1,
                            "fully_correct_instances": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )
            arm = aggregate.summarize_arm("human_skill", root, post)
            self.assertTrue(arm["formula_recalculation_changed_verdict"])
            self.assertEqual(1, arm["network_attempts_denied"])
            self.assertEqual(1, arm["nonzero_tool_exits"])
            serialized = json.dumps(arm)
            self.assertNotIn("private raw command", serialized)

    def test_receipt_does_not_overclaim_skill_benefit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "arm"
            self.make_arm(root, before_pass=True)
            receipt = aggregate.build_receipt([("no_skill", root)], {})
            self.assertFalse(receipt["findings"]["skill_benefit_established"])
            self.assertEqual(
                "NL2SQL", receipt["findings"]["primary_enterprise_domain"]
            )
            self.assertFalse(receipt["raw_traces_or_workbooks_committed"])


if __name__ == "__main__":
    unittest.main()
