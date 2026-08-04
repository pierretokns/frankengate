import copy
import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "tracebench.py"
SPEC = importlib.util.spec_from_file_location("tracebench", MODULE_PATH)
tracebench = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(tracebench)


def fixture(target=False):
    return {
        "instance_id": "example__repo-1",
        "model_name": "example-agent",
        "target": target,
        "trajectory": [
            {
                "role": "system",
                "system_prompt": "Use one command at a time.",
                "text": None,
                "mask": False,
                "cutoff_date": None,
            },
            {
                "role": "user",
                "system_prompt": None,
                "text": "Fix the parser.",
                "mask": False,
                "cutoff_date": None,
            },
            {
                "role": "ai",
                "system_prompt": None,
                "text": "Inspect it.\n```\nopen parser.py 20\n```",
                "mask": True,
                "cutoff_date": None,
            },
            {
                "role": "user",
                "system_prompt": None,
                "text": "File parser.py not found",
                "mask": False,
                "cutoff_date": None,
            },
            {
                "role": "ai",
                "system_prompt": None,
                "text": "Try again.\n```\nopen parser.py 20\n```",
                "mask": True,
                "cutoff_date": None,
            },
            {
                "role": "user",
                "system_prompt": None,
                "text": "File parser.py not found",
                "mask": False,
                "cutoff_date": None,
            },
        ],
        "exit_status": "submitted",
        "generated_patch": "",
        "eval_logs": "1 failed",
    }


class TracebenchTest(unittest.TestCase):
    def test_canonicalization_preserves_every_source_event(self):
        source = fixture()
        canonical = tracebench.canonicalize_nebius(source)
        receipt = canonical["loss_receipt"]
        self.assertEqual(len(source["trajectory"]), len(canonical["events"]))
        self.assertEqual(0, receipt["silently_dropped_event_count"])
        self.assertEqual("tool_call_proposal", canonical["events"][2]["kind"])
        self.assertEqual("reconstructed", canonical["events"][2]["observation_status"])
        self.assertEqual("tool_result", canonical["events"][3]["kind"])
        self.assertEqual("reconstructed", canonical["events"][3]["observation_status"])

    def test_signals_are_outcome_blind(self):
        failure = tracebench.canonicalize_nebius(fixture(target=False))
        success_source = copy.deepcopy(fixture(target=False))
        success_source["target"] = True
        success = tracebench.canonicalize_nebius(success_source)
        self.assertEqual(
            tracebench.deterministic_signals(failure),
            tracebench.deterministic_signals(success),
        )

    def test_repeated_failure_is_detected(self):
        signals = tracebench.deterministic_signals(
            tracebench.canonicalize_nebius(fixture())
        )
        self.assertEqual(1.0, signals["repeated_action_count"])
        self.assertEqual(1.0, signals["immediate_repeat_count"])
        self.assertEqual(2.0, signals["not_found_count"])
        self.assertGreater(signals["friction_score"], 0)

    def test_missing_text_is_safe(self):
        source = fixture()
        source["trajectory"].append(
            {
                "role": "ai",
                "system_prompt": None,
                "text": None,
                "mask": True,
                "cutoff_date": None,
            }
        )
        canonical = tracebench.canonicalize_nebius(source)
        signals = tracebench.deterministic_signals(canonical)
        self.assertEqual(7, len(canonical["events"]))
        self.assertIn("friction_score", signals)

    def test_task_cluster_bootstrap_is_reproducible(self):
        rows = []
        for task_id in ("task-a", "task-b"):
            for failed, score in ((True, 4.0), (False, 1.0)):
                rows.append(
                    {
                        "trace_id": f"{task_id}:{failed}",
                        "task_id": task_id,
                        "failed": failed,
                        "friction_score": score,
                        "turn_count": score,
                    }
                )
        left = tracebench.task_cluster_bootstrap(
            rows,
            ["friction_score", "turn_count"],
            budget_fraction=0.5,
            replicates=10,
            seed=7,
        )
        right = tracebench.task_cluster_bootstrap(
            rows,
            ["friction_score", "turn_count"],
            budget_fraction=0.5,
            replicates=10,
            seed=7,
        )
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
