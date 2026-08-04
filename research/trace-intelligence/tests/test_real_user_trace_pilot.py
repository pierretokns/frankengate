import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "real_user_trace_pilot.py"
)
SPEC = importlib.util.spec_from_file_location("real_user_trace_pilot", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RealUserTracePilotTest(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(
            "main_user",
            MODULE.classify_file(Path("-home-me/session.jsonl")),
        )
        self.assertEqual(
            "benchmark_development",
            MODULE.classify_file(
                Path("-home-me-ht-hyprland-bench/session.jsonl")
            ),
        )
        self.assertEqual(
            "nested_subagent",
            MODULE.classify_file(
                Path(
                    "-home-me/session/subagents/workflows/wf/agent.jsonl"
                )
            ),
        )

    def test_structural_aggregation_does_not_emit_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = root / "-home-me" / "session.jsonl"
            session.parent.mkdir()
            records = [
                {
                    "type": "user",
                    "uuid": "u1",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "SECRET PROMPT"}],
                    },
                },
                {
                    "type": "assistant",
                    "uuid": "a1",
                    "parentUuid": "u1",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "input": {"command": "SECRET COMMAND"},
                            }
                        ],
                    },
                },
                {
                    "type": "user",
                    "uuid": "u2",
                    "parentUuid": "a1",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "is_error": True,
                                "content": "SECRET ERROR",
                            }
                        ],
                    },
                },
                {
                    "type": "user",
                    "uuid": "u3",
                    "parentUuid": "a1",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "is_error": False,
                                "content": "SECRET SUCCESS",
                            }
                        ],
                    },
                },
            ]
            session.write_text(
                "".join(json.dumps(record) + "\n" for record in records)
                + "{invalid",
                encoding="utf-8",
            )
            result = MODULE.analyze_corpus(root, {"dataset_id": "test"})
            serialized = json.dumps(result)

            self.assertNotIn("SECRET", serialized)
            self.assertEqual(4, result["coverage"]["valid_records"])
            self.assertEqual(1, result["coverage"]["invalid_records"])
            self.assertEqual(1, result["lifecycle"]["explicit_error_results"])
            self.assertEqual(1, result["lifecycle"]["recovered_error_episodes"])
            self.assertEqual(1, result["lifecycle"]["branch_points"])


if __name__ == "__main__":
    unittest.main()
