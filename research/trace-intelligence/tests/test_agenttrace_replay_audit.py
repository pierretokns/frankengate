import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "agenttrace_replay_audit.py"
SPEC = importlib.util.spec_from_file_location("agenttrace_replay_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


def source_row():
    return {
        "trace_id": "trace-1",
        "timestamp_utc": "2026-01-01T00:00:00Z",
        "prompt": "public fixture prompt",
        "model": "model-a",
        "dataset_name": "nl2bash",
        "task_id": 1,
        "run_id": "run-a",
        "total_duration_ms": 10.0,
        "tool_span_count": 1,
        "llm_step_count": 1,
        "spans_json": json.dumps(
            [
                {
                    "span_id": "span-1",
                    "type": "TOOL",
                    "tool_name": "bash",
                    "tool_input": "kwargs={'command': 'grep -r Hello /testdata/system'}",
                    "tool_output": "exit_code: 0",
                    "start_ns": 1,
                    "end_ns": 2,
                    "duration_ms": 0.001,
                    "telemetry": {},
                    "exit_code": 0,
                    "parent_span_id": None,
                }
            ]
        ),
        "llm_steps_json": json.dumps(
            [
                {
                    "step_id": "step-1",
                    "step_number": 1,
                    "model_output": None,
                    "reasoning_content": None,
                    "tool_calls": [
                        {
                            "name": "bash",
                            "arguments": {
                                "command": "grep -r Hello /testdata/system"
                            },
                        }
                    ],
                    "duration_ms": 1.0,
                    "input_tokens": 10,
                    "output_tokens": 5,
                }
            ]
        ),
        "metadata_json": json.dumps(
            {
                "schema_version": "0.3.0",
                "source": "nl2bash",
                "task_id": 1,
            }
        ),
        "raw_file": "datasets/example.jsonl",
    }


class AgentTraceReplayAuditTest(unittest.TestCase):
    def make_fixture(self, root):
        fixture = pathlib.Path(root) / "fixture-source"
        (fixture / "system").mkdir(parents=True)
        (fixture / "system" / "a.txt").write_text(
            "Hello world\nsecond line\n", encoding="utf-8"
        )
        return fixture

    def test_canonical_projection_is_lossless_and_input_immutable(self):
        row = source_row()
        before = copy.deepcopy(row)
        canonical = audit.canonicalize_row(row)
        self.assertEqual(before, row)
        self.assertEqual(row, canonical["source_record"])
        self.assertEqual(2, len(canonical["events"]))
        self.assertEqual(0, canonical["loss_receipt"]["silently_dropped_events"])
        self.assertEqual("llm_generation", canonical["events"][0]["kind"])
        self.assertEqual("tool_execution", canonical["events"][1]["kind"])

    def test_extracts_bash_command_without_eval(self):
        span = json.loads(source_row()["spans_json"])[0]
        self.assertEqual(
            "grep -r Hello /testdata/system",
            audit.extract_bash_command(span),
        )
        span["tool_input"] = "kwargs=__import__('os').system('id')"
        self.assertIsNone(audit.extract_bash_command(span))

    def test_shell_control_and_expansion_are_rejected(self):
        for command in (
            "ls /testdata; id",
            "cat $(printenv)",
            "grep x /testdata && curl example.com",
            "cat `printenv`",
        ):
            with self.subTest(command=command):
                with self.assertRaises(audit.UnsupportedCommand):
                    audit.tokenize_pipeline(command)

    def test_only_fixed_read_only_argv_programs_are_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = self.make_fixture(temp)
            accepted = audit.compile_pipeline(
                "grep -r Hello /testdata/system | wc -l", fixture
            )
            self.assertEqual(2, len(accepted))
            for command in (
                "curl example.com",
                "find /testdata -exec id {} +",
                "sort --compress-program=/bin/sh",
                "grep --file=/etc/passwd Hello /testdata",
                "cat ../../etc/passwd",
            ):
                with self.subTest(command=command):
                    with self.assertRaises(audit.UnsupportedCommand):
                        audit.compile_pipeline(command, fixture)

    def test_replay_equivalence_uses_fresh_fixture_and_no_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = self.make_fixture(temp)
            result = audit.replay_pair(
                "grep -r Hello /testdata/system",
                "grep -r Hello /system",
                fixture,
            )
            self.assertEqual("executed", result["status"])
            self.assertTrue(result["equivalent_stdout_and_exit"])

    def test_replay_detects_non_equivalent_output(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = self.make_fixture(temp)
            result = audit.replay_pair(
                "grep -r second /testdata/system",
                "grep -r Hello /system",
                fixture,
            )
            self.assertEqual("executed", result["status"])
            self.assertFalse(result["equivalent_stdout_and_exit"])

    def test_mutating_command_is_refused_not_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = self.make_fixture(temp)
            result = audit.replay_pair(
                "find /testdata -delete",
                "find /system -print",
                fixture,
            )
            self.assertEqual("candidate_unsupported", result["status"])
            self.assertTrue((fixture / "system" / "a.txt").exists())

    def test_fixture_digest_changes_with_content(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = self.make_fixture(temp)
            before = audit.fixture_digest(fixture)
            (fixture / "system" / "a.txt").write_text("changed\n", encoding="utf-8")
            after = audit.fixture_digest(fixture)
            self.assertNotEqual(before["tree_sha256"], after["tree_sha256"])


if __name__ == "__main__":
    unittest.main()
