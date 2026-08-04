import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import trace_commons_memory_conformance as memory  # noqa: E402


def assistant(
    *,
    session_id,
    uuid,
    parent_uuid,
    timestamp,
    tool_id,
    tool,
    tool_input,
):
    return {
        "type": "assistant",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": timestamp,
        "cwd": "C:\\Research",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool,
                    "input": tool_input,
                }
            ]
        },
    }


def tool_result(
    *,
    session_id,
    uuid,
    parent_uuid,
    timestamp,
    assistant_uuid,
    tool_id,
    content,
    is_error=False,
):
    return {
        "type": "user",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": timestamp,
        "sourceToolAssistantUUID": assistant_uuid,
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": content,
                    "is_error": is_error,
                }
            ]
        },
    }


def fixture_records():
    memory_path = (
        "C:\\Users\\USER\\.claude\\projects\\c--Research\\memory\\MEMORY.md"
    )
    project_path = (
        "C:\\Users\\USER\\.claude\\projects\\c--Research\\memory\\project.md"
    )
    first = [
        assistant(
            session_id="session-a",
            uuid="a-read",
            parent_uuid=None,
            timestamp="2026-01-01T00:00:00Z",
            tool_id="tool-read-missing",
            tool="Read",
            tool_input={"file_path": memory_path},
        ),
        tool_result(
            session_id="session-a",
            uuid="u-read",
            parent_uuid="a-read",
            timestamp="2026-01-01T00:00:01Z",
            assistant_uuid="a-read",
            tool_id="tool-read-missing",
            content="file does not exist",
            is_error=True,
        ),
        assistant(
            session_id="session-a",
            uuid="a-write-memory",
            parent_uuid="u-read",
            timestamp="2026-01-01T00:01:00Z",
            tool_id="tool-write-memory",
            tool="Write",
            tool_input={"file_path": memory_path, "content": "# Index\n- fact\n"},
        ),
        tool_result(
            session_id="session-a",
            uuid="u-write-memory",
            parent_uuid="a-write-memory",
            timestamp="2026-01-01T00:01:01Z",
            assistant_uuid="a-write-memory",
            tool_id="tool-write-memory",
            content="created",
        ),
        assistant(
            session_id="session-a",
            uuid="a-write-project",
            parent_uuid="u-write-memory",
            timestamp="2026-01-01T00:02:00Z",
            tool_id="tool-write-project",
            tool="Write",
            tool_input={"file_path": project_path, "content": "alpha\nbeta\n"},
        ),
        tool_result(
            session_id="session-a",
            uuid="u-write-project",
            parent_uuid="a-write-project",
            timestamp="2026-01-01T00:02:01Z",
            assistant_uuid="a-write-project",
            tool_id="tool-write-project",
            content="created",
        ),
    ]
    second = [
        assistant(
            session_id="session-b",
            uuid="b-read-memory",
            parent_uuid=None,
            timestamp="2026-01-02T00:00:00Z",
            tool_id="tool-read-memory",
            tool="Read",
            tool_input={"file_path": memory_path},
        ),
        tool_result(
            session_id="session-b",
            uuid="u-b-read-memory",
            parent_uuid="b-read-memory",
            timestamp="2026-01-02T00:00:01Z",
            assistant_uuid="b-read-memory",
            tool_id="tool-read-memory",
            content="1\t# Index\n2\t- fact\n3\t",
        ),
        assistant(
            session_id="session-b",
            uuid="b-read-project",
            parent_uuid="u-b-read-memory",
            timestamp="2026-01-02T00:01:00Z",
            tool_id="tool-read-project",
            tool="Read",
            tool_input={"file_path": project_path},
        ),
        tool_result(
            session_id="session-b",
            uuid="u-b-read-project",
            parent_uuid="b-read-project",
            timestamp="2026-01-02T00:01:01Z",
            assistant_uuid="b-read-project",
            tool_id="tool-read-project",
            content="1\talpha\n2\tbeta changed\n3\t",
        ),
        assistant(
            session_id="session-b",
            uuid="b-edit-project",
            parent_uuid="u-b-read-project",
            timestamp="2026-01-02T00:02:00Z",
            tool_id="tool-edit-project",
            tool="Edit",
            tool_input={
                "file_path": project_path,
                "old_string": "beta changed",
                "new_string": "beta corrected",
                "replace_all": False,
            },
        ),
        tool_result(
            session_id="session-b",
            uuid="u-b-edit-project",
            parent_uuid="b-edit-project",
            timestamp="2026-01-02T00:02:01Z",
            assistant_uuid="b-edit-project",
            tool_id="tool-edit-project",
            content="updated",
        ),
    ]
    return first, second


def write_fixture(root, records_by_name):
    source_files = []
    for name, records in records_by_name.items():
        path = root / name
        raw = "".join(
            json.dumps(record, sort_keys=True) + "\n" for record in records
        ).encode("utf-8")
        path.write_bytes(raw)
        source_files.append(
            {
                "path": name,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "records": len(records),
            }
        )
    manifest = {
        "schema_version": "trace-dataset-manifest-v1",
        "dataset_id": "synthetic/trace-memory",
        "dataset_revision": "fixture-v1",
        "license": "CC0-1.0",
        "adapter": "claude_native_context_transition_v1",
        "download_policy": {"raw_data_committed": False},
        "cohort": {
            "source_files": source_files,
            "import_authority": {
                "tenant_id": "research",
                "owner_subject_id": "participant",
                "team_id": "study",
                "classification": 1,
                "purpose": "trace-memory-research",
                "authorization_epoch": 3,
            },
        },
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


class TraceCommonsMemoryConformanceTest(unittest.TestCase):
    def test_write_later_read_and_edit_are_loss_aware(self):
        first, second = fixture_records()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = write_fixture(
                root,
                {"session-a.jsonl": first, "session-b.jsonl": second},
            )
            result = memory.analyze_manifest(manifest, root)

        lifecycle = result["memory_lifecycle"]
        self.assertEqual(1, lifecycle["exact_write_to_later_read"])
        self.assertEqual(1, lifecycle["interval_censored_version_gaps"])
        self.assertEqual(1, lifecycle["reconstructable_edits"])
        self.assertEqual(0, lifecycle["failed_operation_promotions"])
        self.assertTrue(result["negative_controls"]["all_passed"])
        self.assertFalse(result["raw_content_emitted"])

    def test_result_before_call_does_not_promote_a_memory_revision(self):
        first, second = fixture_records()
        first[3]["timestamp"] = "2025-12-31T23:59:59Z"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = write_fixture(
                root,
                {"session-a.jsonl": first, "session-b.jsonl": second},
            )
            result = memory.analyze_manifest(manifest, root)

        lifecycle = result["memory_lifecycle"]
        self.assertEqual(1, lifecycle["successful_writes"])
        self.assertEqual(0, lifecycle["exact_write_to_later_read"])
        self.assertEqual(
            lifecycle["context_artifact_calls"] - 1,
            lifecycle["joined_context_artifact_results"],
        )

    def test_aggregate_output_does_not_emit_content_paths_or_tool_ids(self):
        first, second = fixture_records()
        secret = "TOP_SECRET_UNIQUE_MEMORY_VALUE"
        sensitive_path = (
            "C:\\Classified\\Customer-X\\.claude\\projects\\secret\\memory\\"
            "MEMORY.md"
        )
        first[2]["message"]["content"][0]["input"].update(
            {"file_path": sensitive_path, "content": secret + "\n"}
        )
        second[0]["message"]["content"][0]["input"]["file_path"] = sensitive_path
        second[1]["message"]["content"][0]["content"] = f"1\t{secret}\n2\t"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = write_fixture(
                root,
                {"session-a.jsonl": first, "session-b.jsonl": second},
            )
            result = memory.analyze_manifest(manifest, root)

        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(sensitive_path, serialized)
        self.assertNotIn("tool-write-memory", serialized)
        self.assertFalse(result["artifact_paths_emitted"])
        self.assertFalse(result["authority_values_emitted"])

    def test_source_bytes_must_match_the_pinned_receipt(self):
        first, second = fixture_records()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = write_fixture(
                root,
                {"session-a.jsonl": first, "session-b.jsonl": second},
            )
            with (root / "session-a.jsonl").open("ab") as handle:
                handle.write(b" ")
            with self.assertRaisesRegex(
                memory.ConformanceError, "byte length does not match"
            ):
                memory.analyze_manifest(manifest, root)

    def test_snapshot_repetition_is_not_a_memory_revision(self):
        first, second = fixture_records()
        snapshot = {
            "type": "file-history-snapshot",
            "snapshot": {
                "trackedFileBackups": {
                    "C:\\Users\\USER\\.claude\\projects\\c--Research\\"
                    "memory\\MEMORY.md": {
                        "backupFileName": "path-derived@v2",
                        "version": 2,
                        "backupTime": "2026-01-01T00:03:00Z",
                    }
                }
            },
        }
        first.extend([snapshot, dict(snapshot)])
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = write_fixture(
                root,
                {"session-a.jsonl": first, "session-b.jsonl": second},
            )
            result = memory.analyze_manifest(manifest, root)

        snapshots = result["file_history_snapshots"]
        self.assertEqual(2, snapshots["memory_path_mentions"])
        self.assertEqual(1, snapshots["unique_session_scoped_states"])
        self.assertEqual(1, result["memory_lifecycle"]["reconstructable_edits"])
        self.assertEqual(
            0,
            result["memory_lifecycle"]["failed_operation_promotions"],
        )

    def test_authority_requires_exact_tenant_subject_team_purpose_and_epoch(self):
        envelope = memory.AuthorityEnvelope(
            tenant_id="tenant-a",
            owner_subject_id="alice",
            team_id="research",
            classification=2,
            purpose="trace-memory-research",
            authorization_epoch=4,
        )
        allowed = memory.QueryAuthority(
            tenant_id="tenant-a",
            subject_id="alice",
            team_ids=("research",),
            classification_ceiling=2,
            purpose="trace-memory-research",
            authorization_epoch=4,
        )
        self.assertTrue(memory.can_read(envelope, allowed))
        self.assertFalse(
            memory.can_read(
                envelope,
                memory.QueryAuthority(
                    **{**allowed.__dict__, "authorization_epoch": 3}
                ),
            )
        )
        self.assertFalse(
            memory.can_read(
                envelope,
                memory.QueryAuthority(
                    **{**allowed.__dict__, "tenant_id": "tenant-b"}
                ),
            )
        )


if __name__ == "__main__":
    unittest.main()
