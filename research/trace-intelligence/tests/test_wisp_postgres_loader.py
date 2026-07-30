import copy
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wisp_postgres_loader as LOADER  # noqa: E402
from wisp_claude_code_adapter import adapt_wisp_jsonl_bytes  # noqa: E402


def jsonl(*records):
    return b"".join(
        json.dumps(record, separators=(",", ":")).encode("utf-8") + b"\n"
        for record in records
    )


def synthetic_trace():
    return adapt_wisp_jsonl_bytes(
        jsonl(
            {
                "type": "user",
                "uuid": "user-1",
                "sessionId": "session-1",
                "timestamp": "2026-01-01T00:00:03Z",
                "permissionMode": "default",
                "message": {
                    "role": "user",
                    "content": "SYNTHETIC PRIVATE REQUEST",
                },
            },
            {
                "type": "assistant",
                "uuid": "assistant-1",
                "parentUuid": "user-1",
                "sessionId": "session-1",
                "timestamp": "2026-01-01T00:00:04Z",
                "message": {
                    "role": "assistant",
                    "model": "synthetic-model",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call-1",
                            "name": "FixtureTool",
                            "input": {"query": "SYNTHETIC TOOL ARGUMENT"},
                        }
                    ],
                },
            },
            {
                "type": "user",
                "uuid": "result-1",
                "parentUuid": "assistant-1",
                "sessionId": "session-1",
                "timestamp": "2026-01-01T00:00:05Z",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call-1",
                            "content": "SYNTHETIC TOOL FAILURE",
                            "is_error": True,
                        }
                    ],
                },
            },
            {
                "type": "queue-operation",
                "sessionId": "session-1",
                "timestamp": "2026-01-01T00:00:06Z",
                "operation": "enqueue",
                "content": "SYNTHETIC QUEUED CONTENT",
            },
            {
                "type": "file-history-snapshot",
                "timestamp": "2026-01-01T00:00:07Z",
                "messageId": "message-1",
                "snapshot": {"fixture.txt": "SYNTHETIC SNAPSHOT CONTENT"},
            },
        ),
        relative_path="-home-me/session-1.jsonl",
        dataset_id="fixture/wisp",
        dataset_revision="pinned",
    )


def recursively_contains_key(value, forbidden):
    if isinstance(value, dict):
        return any(
            key in forbidden or recursively_contains_key(item, forbidden)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(recursively_contains_key(item, forbidden) for item in value)
    return False


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.executed.append((query, params))
        if "select current_user" in query.lower():
            self.result = (self.connection.current_user,)

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, current_user="trace_research_app"):
        self.current_user = current_user
        self.executed = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


class WispPostgresLoaderTests(unittest.TestCase):
    def test_source_start_time_uses_earliest_source_timestamp(self):
        self.assertEqual(
            dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
            LOADER.source_start_time(
                adapt_wisp_jsonl_bytes(
                    jsonl(
                        {
                            "type": "mode",
                            "sessionId": "s",
                            "timestamp": "2026-01-01T00:00:09Z",
                            "mode": "fixture",
                        },
                        {
                            "type": "permission-mode",
                            "sessionId": "s",
                            "timestamp": "2026-01-01T00:00:00Z",
                            "permissionMode": "default",
                        },
                    ),
                    relative_path="-home-me/s.jsonl",
                )
            ),
        )

    def test_event_jsonb_removes_native_duplicates_and_large_nested_values(self):
        trace = synthetic_trace()
        proposal = next(
            event for event in trace["events"] if event["kind"] == "tool.proposed"
        )
        payload = LOADER.minimize_event_payload(proposal)
        self.assertNotIn("native_record", payload)
        self.assertNotIn("native_block", payload)
        self.assertNotIn("content", payload)
        self.assertEqual(
            {"query": "SYNTHETIC TOOL ARGUMENT"}, payload["arguments"]
        )
        self.assertIn("raw_sha256", payload["source_record_identity"])
        self.assertEqual(
            0, payload["persistence_receipt"]["silent_field_drop_count"]
        )

        queue = next(
            event for event in trace["events"] if event["kind"] == "queue.operation"
        )
        queue_payload = LOADER.minimize_event_payload(queue)
        self.assertNotIn("content", queue_payload["queue_operation"])
        self.assertIn("content_sha256", queue_payload["queue_operation"])
        snapshot = next(
            event
            for event in trace["events"]
            if event["kind"] == "workspace.file_history_snapshot"
        )
        snapshot_payload = LOADER.minimize_event_payload(snapshot)
        self.assertNotIn("snapshot", snapshot_payload["workspace_snapshot"])
        self.assertIn(
            "snapshot_sha256", snapshot_payload["workspace_snapshot"]
        )

    def test_prepared_rows_are_private_content_deduplicated_and_proposal_only(self):
        trace = synthetic_trace()
        prepared = LOADER.prepare_wisp_rows(trace)
        trajectory = prepared["trajectory"]
        self.assertEqual(LOADER.DEFAULT_TENANT_ID, trajectory["tenant_id"])
        self.assertEqual(LOADER.DEFAULT_SUBJECT_ID, trajectory["owner_subject_id"])
        self.assertEqual("private", trajectory["audience"])
        self.assertIsNone(trajectory["team_id"])
        self.assertEqual(
            dt.datetime(2026, 1, 1, 0, 0, 3, tzinfo=dt.timezone.utc),
            trajectory["created_at"],
        )
        self.assertFalse(trajectory["raw_payload"]["raw_transcript_embedded"])
        serialized_reference = json.dumps(trajectory["raw_payload"])
        self.assertNotIn("SYNTHETIC PRIVATE REQUEST", serialized_reference)
        self.assertNotIn("SYNTHETIC TOOL FAILURE", serialized_reference)

        proposal = next(
            event for event in prepared["events"] if event["kind"] == "tool.proposed"
        )
        result = next(
            event for event in prepared["events"] if event["kind"] == "tool.failed"
        )
        self.assertEqual("call-1", proposal["tool_call_id"])
        self.assertEqual("FixtureTool", proposal["tool_name"])
        self.assertEqual(proposal["event_id"], result["parent_event_id"])
        self.assertEqual(
            proposal["event_id"],
            result["payload"]["correlated_tool_proposal_event_id"],
        )
        self.assertEqual("SYNTHETIC TOOL FAILURE", result["content_text"])
        self.assertFalse(
            recursively_contains_key(
                result["payload"], {"native_record", "native_block"}
            )
        )

        self.assertEqual(
            {"signal", "eval_proposal"},
            {artifact["kind"] for artifact in prepared["artifacts"]},
        )
        self.assertNotIn(
            "fact_proposal",
            {artifact["kind"] for artifact in prepared["artifacts"]},
        )
        self.assertNotIn(
            "procedure_proposal",
            {artifact["kind"] for artifact in prepared["artifacts"]},
        )
        valid_ids = {event["event_id"] for event in prepared["events"]}
        serialized_artifacts = json.dumps(prepared["artifacts"])
        self.assertNotIn("SYNTHETIC PRIVATE REQUEST", serialized_artifacts)
        self.assertNotIn("SYNTHETIC TOOL FAILURE", serialized_artifacts)
        for artifact in prepared["artifacts"]:
            self.assertEqual("proposal", artifact["lifecycle"])
            self.assertFalse(artifact["payload"]["automatic_release_allowed"])
            self.assertEqual(
                "human_review_required",
                artifact["payload"]["release_policy"],
            )
            self.assertTrue(
                set(artifact["payload"]["evidence_event_ids"]) <= valid_ids
            )
            if artifact["kind"].endswith("_proposal"):
                self.assertTrue(artifact["payload"]["evidence_event_ids"])
            self.assertIn("artifact=", artifact["content_text"])

    def test_clean_trace_creates_only_signal_and_abstains_from_fact(self):
        trace = adapt_wisp_jsonl_bytes(
            jsonl(
                {
                    "type": "assistant",
                    "uuid": "assistant-1",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "SYNTHETIC"}],
                    },
                }
            ),
            relative_path="-home-me/clean.jsonl",
        )
        artifacts = LOADER.prepare_wisp_rows(trace)["artifacts"]
        self.assertEqual(["signal"], [artifact["kind"] for artifact in artifacts])

    def test_procedure_requires_bounded_same_tool_recovery(self):
        trace = adapt_wisp_jsonl_bytes(
            jsonl(
                {
                    "type": "assistant",
                    "uuid": "assistant-1",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "call-1",
                                "name": "FixtureTool",
                                "input": {},
                            }
                        ],
                    },
                },
                {
                    "type": "user",
                    "uuid": "result-1",
                    "parentUuid": "assistant-1",
                    "timestamp": "2026-01-01T00:00:01Z",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "call-1",
                                "content": "SYNTHETIC FAILURE",
                                "is_error": True,
                            }
                        ],
                    },
                },
                {
                    "type": "assistant",
                    "uuid": "assistant-2",
                    "parentUuid": "result-1",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "call-2",
                                "name": "FixtureTool",
                                "input": {},
                            }
                        ],
                    },
                },
                {
                    "type": "user",
                    "uuid": "result-2",
                    "parentUuid": "assistant-2",
                    "timestamp": "2026-01-01T00:00:03Z",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "call-2",
                                "content": "SYNTHETIC SUCCESS",
                                "is_error": False,
                            }
                        ],
                    },
                },
            ),
            relative_path="-home-me/recovery.jsonl",
        )
        artifacts = LOADER.prepare_wisp_rows(trace)["artifacts"]
        self.assertEqual(
            {"signal", "eval_proposal", "procedure_proposal"},
            {artifact["kind"] for artifact in artifacts},
        )
        procedure = next(
            artifact
            for artifact in artifacts
            if artifact["kind"] == "procedure_proposal"
        )
        self.assertEqual(
            "same_tool_failure_to_success",
            procedure["payload"]["controlled_vocabulary"][
                "recovery_semantics"
            ],
        )
        self.assertEqual(
            LOADER.RECOVERY_MAX_EVENT_DISTANCE,
            procedure["payload"]["controlled_vocabulary"][
                "maximum_event_distance"
            ],
        )
        self.assertEqual(1, procedure["payload"]["bounded_transition_count"])

    def test_preparation_is_deterministic_and_requires_source_time(self):
        trace = synthetic_trace()
        first = LOADER.prepare_wisp_rows(trace)
        second = LOADER.prepare_wisp_rows(copy.deepcopy(trace))
        self.assertEqual(first, second)
        timestamp_free = adapt_wisp_jsonl_bytes(
            jsonl({"type": "mode", "sessionId": "s", "mode": "fixture"}),
            relative_path="-home-me/s.jsonl",
        )
        with self.assertRaisesRegex(
            LOADER.WispPostgresLoaderError, "source start time"
        ):
            LOADER.prepare_wisp_rows(timestamp_free)

    def test_workflow_journal_uses_sibling_source_start(self):
        transcript = adapt_wisp_jsonl_bytes(
            jsonl(
                {
                    "type": "assistant",
                    "uuid": "a",
                    "sessionId": "session-1",
                    "agentId": "agent-1",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {"role": "assistant", "content": []},
                }
            ),
            relative_path=(
                "-home-me/session-1/subagents/workflows/"
                "wf_fixture/agent-agent-1.jsonl"
            ),
        )
        journal = adapt_wisp_jsonl_bytes(
            jsonl({"type": "started", "agentId": "agent-1", "key": "job"}),
            relative_path=(
                "-home-me/session-1/subagents/workflows/wf_fixture/journal.jsonl"
            ),
        )
        starts = LOADER.resolve_source_start_times([journal, transcript])
        expected = dt.datetime(
            2026, 1, 1, 0, 0, 2, tzinfo=dt.timezone.utc
        )
        self.assertEqual(expected, starts[journal["trace_id"]])
        self.assertEqual(expected, starts[transcript["trace_id"]])

    def test_persistence_fails_closed_on_role_and_is_idempotent(self):
        prepared = [LOADER.prepare_wisp_rows(synthetic_trace())]
        with self.assertRaisesRegex(
            LOADER.WispPostgresLoaderError, "trace_research_app"
        ):
            LOADER.persist_prepared_rows(
                FakeConnection(current_user="fixture_admin"), prepared
            )

        connection = FakeConnection()
        calls = []

        def capture(_cursor, query, values, **kwargs):
            calls.append((query, values, kwargs))

        with mock.patch.object(LOADER, "execute_values", side_effect=capture):
            counts = LOADER.persist_prepared_rows(connection, prepared)
        self.assertEqual(
            {
                "source_trajectories": 1,
                "source_events": len(prepared[0]["events"]),
                "signal_artifacts": 1,
                "eval_proposals": 1,
                "fact_proposals": 0,
                "procedure_proposals": 0,
            },
            counts,
        )
        self.assertEqual(3, len(calls))
        self.assertTrue(
            all("on conflict" in query.lower() for query, _values, _kw in calls)
        )
        self.assertTrue(
            all("do nothing" in query.lower() for query, _values, _kw in calls)
        )
        delete_queries = [
            (query, params)
            for query, params in connection.executed
            if "delete from trace_research.derived_artifacts" in query.lower()
        ]
        self.assertEqual(1, len(delete_queries))
        self.assertEqual(
            LOADER.DERIVATION_REVISION, delete_queries[0][1][0]
        )
        self.assertEqual(
            [prepared[0]["trajectory"]["id"]], delete_queries[0][1][1]
        )
        self.assertIn("created_at", calls[0][0])
        self.assertIn("lifecycle", calls[-1][0])
        self.assertEqual(1, connection.commits)

    def test_cli_defaults_are_private(self):
        args = LOADER.build_parser().parse_args(
            [
                "--dsn",
                "fixture",
                "--corpus-root",
                "/synthetic/corpus",
                "--manifest",
                "/synthetic/manifest.json",
            ]
        )
        self.assertEqual("private", args.audience)
        self.assertEqual(LOADER.DEFAULT_TENANT_ID, args.tenant_id)
        self.assertEqual(LOADER.DEFAULT_SUBJECT_ID, args.subject_id)
        self.assertIsNone(args.team_id)


if __name__ == "__main__":
    unittest.main()
