import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "public_native_history_fidelity.py"
)
SPEC = importlib.util.spec_from_file_location(
    "public_native_history_fidelity", MODULE_PATH
)
fidelity = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = fidelity
SPEC.loader.exec_module(fidelity)


def write_jsonl(path, rows, malformed=False):
    text = "".join(json.dumps(row) + "\n" for row in rows)
    if malformed:
        text += "{bad json\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class PublicNativeHistoryFidelityTest(unittest.TestCase):
    def test_scanner_emits_counts_not_values(self):
        scanner = fidelity.AggregateScanner()
        scanner.scan(
            {
                "redacted": "<API_KEY_1>",
                "candidate": "sk-proj-abcdefghijklmnopqrstuvwxyz012345",
            }
        )
        aggregate = scanner.aggregate()
        self.assertEqual(
            1,
            aggregate["redaction_evidence"]["numbered_typed_placeholder"],
        )
        self.assertEqual(1, aggregate["possible_secret_regex_candidate_total"])
        serialized = json.dumps(aggregate)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", serialized)

    def test_correlation_separates_exact_ambiguous_and_unresolved(self):
        calls = {("s", "a"): 1, ("s", "b"): 2, ("s", "c"): 1}
        results = {("s", "a"): 1, ("s", "b"): 1, ("s", "d"): 1}
        result = fidelity.correlation(calls, results)
        self.assertEqual(2, result["matched_by_id"])
        self.assertEqual(1, result["one_to_one_id_joins"])
        self.assertEqual(1, result["ambiguous_reused_ids"])
        self.assertEqual(2, result["unresolved_calls"])
        self.assertEqual(1, result["unresolved_results"])

    def test_all_adapters_are_aggregate_only_and_classified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            mike = root / "mike"
            write_jsonl(
                mike / "sessions" / "one.jsonl",
                [
                    {
                        "schema_version": 1,
                        "session_id": "secret-session",
                        "record_index": 0,
                        "timestamp": "2026-01-01T00:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": "secret-session",
                            "model": "model",
                            "thread_source": "exec",
                        },
                    },
                    {
                        "schema_version": 1,
                        "session_id": "secret-session",
                        "record_index": 1,
                        "timestamp": "2026-01-01T00:00:01Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "tool",
                            "arguments": "private-argument",
                        },
                    },
                ],
                malformed=True,
            )
            (mike / "dataset_manifest.json").write_text(
                json.dumps(
                    {
                        "selected_session_count": 1,
                        "published_record_count": 2,
                        "redaction_count": 0,
                        "dropped_record_count": 0,
                        "truncated_field_count": 0,
                    }
                ),
                encoding="utf-8",
            )

            alin = root / "alin"
            write_jsonl(
                alin / "one.jsonl",
                [
                    {
                        "type": "assistant",
                        "sessionId": "alin-session",
                        "uuid": "assistant-id",
                        "parentUuid": "root-id",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "cwd": "/private/path",
                        "message": {
                            "model": "model",
                            "usage": {},
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call-id",
                                    "name": "tool",
                                    "input": "private-input",
                                }
                            ],
                        },
                    },
                    {
                        "type": "user",
                        "sessionId": "alin-session",
                        "uuid": "root-id",
                        "timestamp": "2026-01-01T00:00:01Z",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "call-id",
                                    "content": "private-output",
                                }
                            ]
                        },
                    },
                ],
            )
            (alin / "manifest.json").write_text(
                json.dumps(
                    {
                        "totals": {
                            "published_files": 1,
                            "published_rows": 2,
                            "source_rows": 2,
                            "excluded_rows": 0,
                            "scrub_total": 1,
                        },
                        "policy": {"deterministic": True},
                    }
                ),
                encoding="utf-8",
            )

            ranga = root / "ranga"
            write_jsonl(
                ranga / "sessions.jsonl",
                [
                    {
                        "id": "ranga-session",
                        "source": "codex",
                        "projectPath": "/private/project",
                        "messages": [
                            {
                                "role": "assistant",
                                "content": "private-input",
                                "toolCallId": "call",
                                "timestamp": "2026-01-01T00:00:00Z",
                            },
                            {
                                "role": "tool-result",
                                "content": "private-output",
                                "toolCallId": "call",
                                "timestamp": "2026-01-01T00:00:01Z",
                            },
                        ],
                    }
                ],
            )
            (ranga / "manifest.json").write_text(
                json.dumps(
                    {"metadata": {"sessionCount": 1, "messageCount": 2}}
                ),
                encoding="utf-8",
            )

            cfahlgren = root / "cfahlgren"
            raw_rows = [
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "cf-session",
                        "model_provider": "provider",
                        "cwd": "/private/project",
                    },
                },
                {
                    "timestamp": "2026-01-01T00:00:01Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "call_id": "call",
                        "name": "tool",
                        "arguments": "private-input",
                    },
                },
                {
                    "timestamp": "2026-01-01T00:00:02Z",
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "call_id": "call",
                        "output": "private-output",
                    },
                },
            ]
            raw_path = cfahlgren / "rollout-one.jsonl"
            write_jsonl(raw_path, raw_rows)
            write_jsonl(
                cfahlgren / "sessions.jsonl",
                [
                    {
                        "session_id": "cf-session",
                        "file_name": raw_path.name,
                        "raw_jsonl": raw_path.read_text(encoding="utf-8"),
                    }
                ],
            )

            dataclaw = root / "dataclaw"
            write_jsonl(
                dataclaw / "conversations.jsonl",
                [
                    {
                        "session_id": "dc-session",
                        "project": "private-project",
                        "model": "model",
                        "start_time": "2026-01-01T00:00:00Z",
                        "end_time": "2026-01-01T00:01:00Z",
                        "stats": {},
                        "messages": [
                            {
                                "role": "assistant",
                                "thinking": "private-thought",
                                "timestamp": "2026-01-01T00:00:01Z",
                                "tool_uses": [
                                    {"tool": "tool", "input": "private-input"}
                                ],
                            }
                        ],
                    }
                ],
            )
            (dataclaw / "metadata.json").write_text(
                json.dumps(
                    {
                        "sessions": 1,
                        "projects": ["private-project"],
                        "redactions": 1,
                        "skipped": 0,
                    }
                ),
                encoding="utf-8",
            )

            jobseek = root / "jobseek"
            write_jsonl(
                jobseek / "traces" / "private-company" / "trace.jsonl",
                [
                    {"_trace_header": True, "record_count": 2},
                    {
                        "type": "assistant",
                        "uuid": "assistant",
                        "parentUuid": "root",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "isSidechain": True,
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call",
                                    "name": "tool",
                                    "input": "private-input",
                                }
                            ]
                        },
                    },
                    {
                        "type": "user",
                        "uuid": "root",
                        "timestamp": "2026-01-01T00:00:01Z",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "call",
                                    "content": "private-output",
                                }
                            ]
                        },
                    },
                ],
            )

            wisp_structural = root / "wisp-structural.json"
            wisp_structural.write_text(
                json.dumps(
                    {
                        "coverage": {
                            "jsonl_files": 1,
                            "valid_records": 2,
                            "invalid_records": 0,
                            "files_by_stratum": {
                                "main_user": 1,
                                "benchmark_development": 0,
                                "benchmark_task": 0,
                                "nested_subagent": 0,
                            },
                            "record_types": {"assistant": 1, "user": 1},
                        },
                        "lifecycle": {
                            "tool_uses": 1,
                            "tool_results": 1,
                            "branch_points": 0,
                            "dangling_parent_references": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            wisp_conformance = root / "wisp-conformance.json"
            wisp_conformance.write_text(
                json.dumps(
                    {
                        "source": {
                            "dataset_id": "wisp",
                            "dataset_revision": "revision",
                            "license": "MIT",
                        },
                        "tool_result_correlation": {
                            "exact_unique_prior": 1,
                            "unresolved": 0,
                        },
                        "privacy_contract": {
                            "aggregate_counts_only": True
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = fidelity.build_result(
                mike,
                alin,
                ranga,
                cfahlgren,
                dataclaw,
                jobseek,
                wisp_structural,
                wisp_conformance,
            )
            serialized = json.dumps(result)
            for forbidden in (
                temporary,
                "secret-session",
                "private-input",
                "private-output",
                "private-thought",
                "private-company",
            ):
                self.assertNotIn(forbidden, serialized)
            self.assertEqual(
                1,
                result["datasets"]["alin_claude"]["message_and_tool_structure"][
                    "call_result_join"
                ]["one_to_one_id_joins"],
            )
            self.assertEqual(
                1,
                result["datasets"]["cfahlgren_codex"]["inventory"][
                    "derived_rows_byte_equal_to_raw_file"
                ],
            )
            self.assertEqual(
                1,
                result["datasets"]["mike_codex"]["inventory"][
                    "malformed_records"
                ],
            )
            self.assertFalse(
                result["datasets"]["dataclaw_peter"]["longitudinal_scope"][
                    "independent_user_cohort"
                ]
            )
            self.assertEqual([], result["classification"]["complete_harness_home"])


if __name__ == "__main__":
    unittest.main()
