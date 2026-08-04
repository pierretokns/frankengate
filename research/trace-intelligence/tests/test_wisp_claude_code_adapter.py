import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wisp_claude_code_adapter import (  # noqa: E402
    WispAdapterError,
    adapt_wisp_file,
    adapt_wisp_jsonl_bytes,
    assert_no_silent_drops,
    canonicalize_wisp_file,
    classify_relative_path,
    parse_path_context,
)


def jsonl(*records):
    return b"".join(
        json.dumps(record, separators=(",", ":")).encode("utf-8") + b"\n"
        if isinstance(record, dict)
        else record
        for record in records
    )


def event_by_kind(trajectory, kind):
    return [event for event in trajectory["events"] if event["kind"] == kind]


class WispClaudeCodeAdapterTests(unittest.TestCase):
    def test_path_strata_and_subagent_workflow_lineage(self):
        path = (
            "-synthetic-project/session-1/subagents/workflows/"
            "wf_fixture/agent-a_fixture.jsonl"
        )
        context = parse_path_context(path)
        self.assertEqual("nested_subagent", classify_relative_path(path))
        self.assertTrue(context["is_subagent_workflow"])
        self.assertEqual("session-1", context["parent_session_id"])
        self.assertEqual("wf_fixture", context["workflow_id"])
        self.assertEqual("a_fixture", context["agent_file_id"])
        self.assertEqual("agent_transcript", context["workflow_file_role"])
        self.assertEqual(
            "main_user", classify_relative_path("-home-me/session.jsonl")
        )
        self.assertEqual(
            "benchmark_development",
            classify_relative_path("-home-me-ht-hyprland-bench/session.jsonl"),
        )
        self.assertEqual(
            "benchmark_task",
            classify_relative_path(
                "-home-me-ht-hyprland-bench-results-fixture/session.jsonl"
            ),
        )

    def test_message_dag_content_blocks_and_tool_correlation_are_preserved(self):
        records = [
            {
                "type": "user",
                "uuid": "user-1",
                "parentUuid": None,
                "sessionId": "session-1",
                "timestamp": "2026-01-01T00:00:00Z",
                "permissionMode": "default",
                "message": {
                    "role": "user",
                    "content": "SYNTHETIC REQUEST",
                },
            },
            {
                "type": "assistant",
                "uuid": "assistant-1",
                "parentUuid": "user-1",
                "sessionId": "session-1",
                "timestamp": "2026-01-01T00:00:01Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "SYNTHETIC REASONING",
                            "signature": "fixture-signature",
                        },
                        {"type": "text", "text": "SYNTHETIC RESPONSE"},
                        {
                            "type": "tool_use",
                            "id": "call-1",
                            "name": "FixtureTool",
                            "input": {"value": "SYNTHETIC ARGUMENT"},
                            "caller": {"type": "direct"},
                        },
                    ],
                },
            },
            {
                "type": "user",
                "uuid": "result-1",
                "parentUuid": "assistant-1",
                "sessionId": "session-1",
                "timestamp": "2026-01-01T00:00:02Z",
                "sourceToolAssistantUUID": "assistant-1",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call-1",
                            "content": "SYNTHETIC TOOL OUTPUT",
                            "is_error": False,
                        }
                    ],
                },
            },
        ]
        raw = jsonl(*records)
        trajectory = adapt_wisp_jsonl_bytes(
            raw, relative_path="-home-me/session-1.jsonl"
        )
        assert_no_silent_drops(trajectory)

        base = [
            event
            for event in trajectory["events"]
            if event["source_record_identity"].get("uuid") == "assistant-1"
            and event["kind"] == "conversation.message"
        ][0]
        user_base = [
            event
            for event in trajectory["events"]
            if event["source_record_identity"].get("uuid") == "user-1"
            and event["kind"] == "conversation.message"
        ][0]
        self.assertEqual(user_base["event_id"], base["parent_event_id"])
        self.assertEqual(records[1], base["native_record"])
        self.assertEqual(
            hashlib.sha256(raw.splitlines(keepends=True)[1]).hexdigest(),
            base["source_record_identity"]["raw_sha256"],
        )

        self.assertEqual(
            "SYNTHETIC REASONING",
            event_by_kind(trajectory, "model.thinking")[0]["content"],
        )
        self.assertEqual(
            "SYNTHETIC RESPONSE",
            event_by_kind(trajectory, "conversation.content.text")[-1]["content"],
        )
        proposal = event_by_kind(trajectory, "tool.proposed")[0]
        result = event_by_kind(trajectory, "tool.completed")[0]
        self.assertEqual("call-1", proposal["tool_call_id"])
        self.assertEqual(proposal["event_id"], result["parent_event_id"])
        self.assertEqual(
            proposal["event_id"], result["correlated_tool_proposal_event_id"]
        )
        self.assertEqual("exact_unique_prior", result["correlation_status"])
        self.assertEqual(4, trajectory["loss_receipt"]["source_content_block_count"])
        self.assertEqual(
            4, trajectory["loss_receipt"]["accounted_source_content_block_count"]
        )

    def test_session_compaction_queue_snapshot_mode_and_permission_metadata(self):
        records = [
            {
                "type": "user",
                "uuid": "compact-1",
                "sessionId": "session-1",
                "isCompactSummary": True,
                "permissionMode": "bypassPermissions",
                "message": {"role": "user", "content": "SYNTHETIC SUMMARY"},
            },
            {
                "type": "system",
                "uuid": "system-1",
                "sessionId": "session-1",
                "subtype": "compact_boundary",
                "compactMetadata": {"trigger": "fixture"},
                "retractedMessageUuids": ["old-1"],
                "content": "SYNTHETIC SYSTEM EVENT",
            },
            {
                "type": "queue-operation",
                "sessionId": "session-1",
                "operation": "enqueue",
                "timestamp": "2026-01-01T00:00:00Z",
                "content": "SYNTHETIC QUEUED REQUEST",
            },
            {
                "type": "file-history-snapshot",
                "messageId": "message-1",
                "isSnapshotUpdate": True,
                "snapshot": {"tracked": {"fixture.txt": "synthetic-state"}},
            },
            {"type": "mode", "sessionId": "session-1", "mode": "acceptEdits"},
            {
                "type": "permission-mode",
                "sessionId": "session-1",
                "permissionMode": "default",
            },
        ]
        trajectory = adapt_wisp_jsonl_bytes(
            jsonl(*records), relative_path="-home-me/session-1.jsonl"
        )
        self.assertTrue(
            event_by_kind(trajectory, "conversation.message")[0]["compaction"][
                "is_compact_summary"
            ]
        )
        system = event_by_kind(trajectory, "system.event")[0]
        self.assertEqual("compact_boundary", system["system_semantics"]["subtype"])
        self.assertEqual(
            "enqueue",
            event_by_kind(trajectory, "queue.operation")[0]["queue_operation"][
                "operation"
            ],
        )
        snapshot = event_by_kind(
            trajectory, "workspace.file_history_snapshot"
        )[0]
        self.assertTrue(snapshot["workspace_snapshot"]["is_update"])
        self.assertEqual(
            "acceptEdits",
            event_by_kind(trajectory, "session.mode")[0]["interaction_policy"][
                "mode"
            ],
        )
        self.assertEqual(
            "default",
            event_by_kind(
                trajectory, "session.permission_mode"
            )[0]["interaction_policy"]["permission_mode"],
        )
        assert_no_silent_drops(trajectory)

    def test_subagent_journal_records_retain_workflow_and_agent_lineage(self):
        path = (
            "-synthetic-project/session-1/subagents/workflows/"
            "wf_fixture/journal.jsonl"
        )
        trajectory = adapt_wisp_jsonl_bytes(
            jsonl(
                {"type": "started", "agentId": "a_fixture", "key": "job-1"},
                {
                    "type": "result",
                    "agentId": "a_fixture",
                    "key": "job-1",
                    "result": "SYNTHETIC RESULT",
                },
            ),
            relative_path=path,
        )
        started = event_by_kind(trajectory, "subagent.started")[0]
        completed = event_by_kind(trajectory, "subagent.result")[0]
        for event in (started, completed):
            self.assertEqual(
                "session-1", event["subagent_workflow"]["parent_session_id"]
            )
            self.assertEqual(
                "wf_fixture", event["subagent_workflow"]["workflow_id"]
            )
            self.assertEqual("a_fixture", event["subagent_workflow"]["agent_id"])
        self.assertEqual("journal", started["path_context"]["workflow_file_role"])

    def test_malformed_unknown_and_dangling_inputs_have_explicit_receipts(self):
        source = jsonl(
            {
                "type": "future-record",
                "uuid": "future-1",
                "parentUuid": "missing-parent",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "future-block", "value": "SYNTHETIC VALUE"},
                        ["SYNTHETIC NON-OBJECT BLOCK"],
                    ],
                },
                "futureField": {"kept": True},
            },
            b"{malformed synthetic json\n",
        )
        trajectory = adapt_wisp_jsonl_bytes(
            source, relative_path="-synthetic-project/session.jsonl"
        )
        receipt = trajectory["loss_receipt"]
        categories = {item["category"] for item in receipt["unknowns"]}
        self.assertIn("unknown_record_type", categories)
        self.assertIn("dangling_parent_uuid", categories)
        self.assertIn("unknown_content_block_type", categories)
        self.assertIn("non_object_content_block", categories)
        self.assertEqual(
            ["malformed_source_bytes_not_retained"],
            [item["category"] for item in receipt["losses"]],
        )
        unknown_base = event_by_kind(trajectory, "source.unknown_record")[0]
        self.assertEqual(
            {"kept": True}, unknown_base["native_record"]["futureField"]
        )
        malformed = event_by_kind(trajectory, "source.malformed_record")[0]
        self.assertNotIn("native_record", malformed)
        self.assertEqual("raw_source_not_retained", malformed["loss_status"])
        self.assertEqual(2, receipt["source_record_count"])
        self.assertEqual(2, receipt["accounted_source_record_count"])
        self.assertEqual(0, receipt["silently_dropped_record_count"])
        self.assertEqual(0, receipt["silently_dropped_content_block_count"])
        assert_no_silent_drops(trajectory)

    def test_adapt_file_enforces_corpus_boundary_and_file_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            corpus.mkdir()
            source = corpus / "fixture.jsonl"
            content = jsonl(
                {
                    "type": "assistant",
                    "uuid": "assistant-1",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "SYNTHETIC"}],
                    },
                }
            )
            source.write_bytes(content)
            trajectory = adapt_wisp_file(source, corpus_root=corpus)
            self.assertEqual(
                hashlib.sha256(content).hexdigest(),
                trajectory["source"]["source_file_sha256"],
            )
            outside = root / "outside.jsonl"
            outside.write_bytes(content)
            with self.assertRaises(WispAdapterError):
                adapt_wisp_file(outside, corpus_root=corpus)

    def test_stable_loader_api_uses_pinned_manifest_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "session.jsonl"
            source.write_bytes(
                jsonl(
                    {
                        "type": "mode",
                        "sessionId": "session-1",
                        "mode": "fixture",
                    }
                )
            )
            manifest = {
                "schema_version": "trace-dataset-manifest-v1",
                "dataset_id": "fixture/wisp",
                "dataset_revision": "pinned-revision",
            }
            trajectory = canonicalize_wisp_file(source, root, manifest)
            self.assertEqual("fixture/wisp", trajectory["source"]["dataset_id"])
            self.assertEqual(
                "pinned-revision", trajectory["source"]["dataset_revision"]
            )
            self.assertEqual(
                "trace-dataset-manifest-v1",
                trajectory["source"]["manifest_schema_version"],
            )
            assert_no_silent_drops(trajectory)

    def test_assertion_rejects_falsified_accounting(self):
        trajectory = adapt_wisp_jsonl_bytes(
            jsonl({"type": "mode", "sessionId": "s", "mode": "fixture"}),
            relative_path="-synthetic-project/session.jsonl",
        )
        trajectory["loss_receipt"]["accounted_source_record_count"] = 0
        with self.assertRaisesRegex(WispAdapterError, "accounting mismatch"):
            assert_no_silent_drops(trajectory)


if __name__ == "__main__":
    unittest.main()
