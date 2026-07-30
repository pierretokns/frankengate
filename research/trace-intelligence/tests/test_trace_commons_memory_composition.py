import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import trace_commons_memory_composition as composition  # noqa: E402
import trace_commons_memory_conformance as native  # noqa: E402


SECRET = "DO-NOT-EMIT-memory-value-7f46dcbe"
MEMORY_PATH = (
    "C:\\Users\\USER\\.claude\\projects\\c--Research\\memory\\MEMORY.md"
)


def assistant(
    *,
    session_id,
    uuid,
    parent_uuid,
    timestamp,
    tool_id,
    tool,
    tool_input,
    cwd="C:\\Research",
):
    return {
        "type": "assistant",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": timestamp,
        "cwd": cwd,
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
    cwd="C:\\Research",
):
    return {
        "type": "user",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": timestamp,
        "cwd": cwd,
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


def write_source(root, name, records):
    path = root / name
    raw = "".join(
        json.dumps(record, sort_keys=True) + "\n" for record in records
    ).encode("utf-8")
    path.write_bytes(raw)
    return {
        "path": name,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "records": len(records),
    }


def write_manifest(root, sources):
    manifest = {
        "schema_version": "trace-dataset-manifest-v1",
        "dataset_id": "synthetic/trace-commons-composition",
        "dataset_revision": "fixture-v1",
        "license": "CC0-1.0",
        "adapter": "claude_native_context_transition_v1",
        "download_policy": {"raw_data_committed": False},
        "cohort": {
            "source_files": sources,
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
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def exact_write_read_fixture(root):
    first = [
        assistant(
            session_id="session-a",
            uuid="a-write",
            parent_uuid=None,
            timestamp="2026-01-01T00:00:00Z",
            tool_id="tool-write",
            tool="Write",
            tool_input={"file_path": MEMORY_PATH, "content": SECRET},
        ),
        tool_result(
            session_id="session-a",
            uuid="u-write",
            parent_uuid="a-write",
            timestamp="2026-01-01T00:00:01Z",
            assistant_uuid="a-write",
            tool_id="tool-write",
            content="created",
        ),
    ]
    second = [
        assistant(
            session_id="session-b",
            uuid="b-read",
            parent_uuid=None,
            timestamp="2026-01-02T00:00:00Z",
            tool_id="tool-read",
            tool="Read",
            tool_input={"file_path": MEMORY_PATH},
        ),
        tool_result(
            session_id="session-b",
            uuid="u-read",
            parent_uuid="b-read",
            timestamp="2026-01-02T00:00:01Z",
            assistant_uuid="b-read",
            tool_id="tool-read",
            content=f"1\t{SECRET}\n2\t",
        ),
    ]
    sources = [
        write_source(root, "session-a.jsonl", first),
        write_source(root, "session-b.jsonl", second),
    ]
    return write_manifest(root, sources)


def changed_history_fixture(root):
    records = [
        (
            "session-a.jsonl",
            [
                assistant(
                    session_id="session-a",
                    uuid="a-write",
                    parent_uuid=None,
                    timestamp="2026-01-01T00:00:00Z",
                    tool_id="a-tool-write",
                    tool="Write",
                    tool_input={
                        "file_path": MEMORY_PATH,
                        "content": "version one",
                    },
                ),
                tool_result(
                    session_id="session-a",
                    uuid="a-result",
                    parent_uuid="a-write",
                    timestamp="2026-01-01T00:00:01Z",
                    assistant_uuid="a-write",
                    tool_id="a-tool-write",
                    content="created",
                ),
            ],
        ),
        (
            "session-b.jsonl",
            [
                assistant(
                    session_id="session-b",
                    uuid="b-read",
                    parent_uuid=None,
                    timestamp="2026-01-02T00:00:00Z",
                    tool_id="b-tool-read",
                    tool="Read",
                    tool_input={"file_path": MEMORY_PATH},
                ),
                tool_result(
                    session_id="session-b",
                    uuid="b-result",
                    parent_uuid="b-read",
                    timestamp="2026-01-02T00:00:01Z",
                    assistant_uuid="b-read",
                    tool_id="b-tool-read",
                    content="1\tversion one\n2\t",
                ),
            ],
        ),
        (
            "session-c.jsonl",
            [
                assistant(
                    session_id="session-c",
                    uuid="c-write",
                    parent_uuid=None,
                    timestamp="2026-01-03T00:00:00Z",
                    tool_id="c-tool-write",
                    tool="Write",
                    tool_input={
                        "file_path": MEMORY_PATH,
                        "content": "version two",
                    },
                ),
                tool_result(
                    session_id="session-c",
                    uuid="c-result",
                    parent_uuid="c-write",
                    timestamp="2026-01-03T00:00:01Z",
                    assistant_uuid="c-write",
                    tool_id="c-tool-write",
                    content="updated",
                ),
            ],
        ),
        (
            "session-d.jsonl",
            [
                assistant(
                    session_id="session-d",
                    uuid="d-read",
                    parent_uuid=None,
                    timestamp="2026-01-04T00:00:00Z",
                    tool_id="d-tool-read",
                    tool="Read",
                    tool_input={"file_path": MEMORY_PATH},
                ),
                tool_result(
                    session_id="session-d",
                    uuid="d-result",
                    parent_uuid="d-read",
                    timestamp="2026-01-04T00:00:01Z",
                    assistant_uuid="d-read",
                    tool_id="d-tool-read",
                    content="1\tversion two\n2\t",
                ),
            ],
        ),
    ]
    sources = [
        write_source(root, name, source_records)
        for name, source_records in records
    ]
    return write_manifest(root, sources)


class TraceCommonsMemoryCompositionTest(unittest.TestCase):
    def test_cutoff_safe_project_identity_ignores_future_cwd(self):
        records = [
            assistant(
                session_id="session-a",
                uuid="read",
                parent_uuid=None,
                timestamp="2026-01-01T00:00:00Z",
                tool_id="tool-read",
                tool="Read",
                tool_input={"file_path": MEMORY_PATH},
                cwd="",
            ),
            tool_result(
                session_id="session-a",
                uuid="result",
                parent_uuid="read",
                timestamp="2026-01-01T00:00:01Z",
                assistant_uuid="read",
                tool_id="tool-read",
                content="1\tvalue\n2\t",
                cwd="",
            ),
            {
                "type": "system",
                "sessionId": "session-a",
                "uuid": "future-context",
                "parentUuid": "result",
                "timestamp": "2026-01-01T00:01:00Z",
                "cwd": "C:\\Future",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = write_manifest(
                root,
                [write_source(root, "source.jsonl", records)],
            )
            cohort = native.load_verified_memory_cohort(
                manifest,
                root,
                default_authority=composition.FIXED_IMPORT_AUTHORITY,
            )
            identity_key = hashlib.sha256(b"cutoff-safe-test").digest()
            interactions, _ = composition._qualifying_interactions(
                cohort,
                identity_key,
                {"source.jsonl": 0},
                cutoff_safe_project_identity=True,
            )

        self.assertEqual(1, len(interactions))
        self.assertEqual("", interactions[0].project_source)

    def test_project_normalization_casefolds_windows_but_not_posix(self):
        self.assertEqual(
            "d:/epilog",
            composition.normalize_project_source("D:\\Epilog\\"),
        )
        self.assertEqual(
            "/Users/USER/ComparIA",
            composition.normalize_project_source("/Users/USER/ComparIA/"),
        )
        self.assertNotEqual(
            composition.normalize_project_source("/Users/USER/ComparIA"),
            composition.normalize_project_source("/users/user/comparia"),
        )

    def test_exact_write_then_read_is_compared_without_emitting_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = exact_write_read_fixture(root)
            first = composition.analyze_manifest(manifest, root)
            second = composition.analyze_manifest(manifest, root)

        self.assertEqual(first, second)
        self.assertEqual(2, first["discovery"]["histories"])
        self.assertEqual(2, first["discovery"]["qualifying_interactions"])
        self.assertEqual(1, first["evaluation"]["online_queries"])
        self.assertEqual(
            1,
            first["evaluation"][
                "exact_cross_session_write_to_later_read"
            ],
        )
        for arm in ("verbatim", "latest_only", "contextual_bitemporal"):
            self.assertEqual(
                {"numerator": 1, "denominator": 1, "rate": 1.0},
                first["mechanisms"][arm]["online_exact"],
            )
        self.assertEqual(
            0,
            first["mechanisms"]["proposal_only_dream"][
                "automatically_active_changes"
            ],
        )
        self.assertEqual(
            "not_run",
            first["mechanisms"]["proposal_only_dream"][
                "failed_job_atomicity_control"
            ]["status"],
        )
        self.assertIsNone(
            first["mechanisms"]["proposal_only_dream"][
                "failed_job_atomicity_control"
            ]["exposed_proposals"],
        )
        self.assertEqual(
            "partial_active_isolation_only_failed_job_control_not_run",
            first["decision_status"]["proposal_isolation_h4"],
        )
        self.assertEqual(
            2,
            first["transitions"]["supported_observations"],
        )
        self.assertEqual(
            1,
            first["transitions"]["unique_supported_revisions"],
        )
        self.assertFalse(first["content_policy"]["raw_content_emitted"])
        self.assertFalse(
            first["decision_status"]["comparative_quality_claim_allowed"]
        )
        self.assertEqual(
            "not_run", first["decision_status"]["model_quality_phase"]
        )
        self.assertNotIn(SECRET, json.dumps(first, sort_keys=True))
        self.assertNotIn(SECRET, composition.render_markdown(first))

    def test_longitudinal_gate_metrics_emit_counts_without_project_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = exact_write_read_fixture(root)
            metrics = composition.longitudinal_gate_metrics(manifest, root)

        self.assertEqual(
            {
                "cases": 1,
                "project_contexts": 1,
                "cases_per_project_desc": [1],
            },
            metrics["online_queries"],
        )
        self.assertEqual(
            1,
            metrics["exact_cross_session_write_to_later_read"]["cases"],
        )
        self.assertEqual(
            1,
            metrics["exact_cross_session_write_to_later_read"][
                "distinct_session_pairs"
            ],
        )
        self.assertEqual(
            1,
            metrics["exact_cross_session_write_to_later_read"][
                "distinct_context_artifacts"
            ],
        )
        serialized = json.dumps(metrics, sort_keys=True)
        self.assertNotIn("session-a", serialized)
        self.assertNotIn("session-b", serialized)
        self.assertNotIn(SECRET, serialized)
        self.assertFalse(metrics["native_paths_emitted"])
        self.assertFalse(metrics["native_identifiers_emitted"])
        self.assertFalse(metrics["project_digests_emitted"])

    def test_bitemporal_retains_an_earlier_state_that_latest_only_loses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = changed_history_fixture(root)
            result = composition.analyze_manifest(manifest, root)

        self.assertEqual(
            2,
            result["evaluation"]["post_observation_retention_queries"],
        )
        self.assertEqual(
            1,
            result["evaluation"][
                "changed_artifact_post_observation_cases"
            ],
        )
        self.assertEqual(
            {"numerator": 2, "denominator": 2, "rate": 1.0},
            result["mechanisms"]["verbatim"][
                "post_observation_retention_exact"
            ],
        )
        self.assertEqual(
            {"numerator": 1, "denominator": 2, "rate": 0.5},
            result["mechanisms"]["latest_only"][
                "post_observation_retention_exact"
            ],
        )
        self.assertEqual(
            {"numerator": 2, "denominator": 2, "rate": 1.0},
            result["mechanisms"]["contextual_bitemporal"][
                "post_observation_retention_exact"
            ],
        )
        self.assertGreater(
            result["mechanisms"]["latest_only"]["overwritten_revisions"],
            0,
        )

    def test_latest_only_is_global_but_contextual_arms_do_not_cross_projects(self):
        project_a_path = "C:\\A\\memory\\MEMORY.md"
        project_b_path = "C:\\B\\memory\\MEMORY.md"
        sources_by_name = {
            "a.jsonl": [
                assistant(
                    session_id="a",
                    uuid="a-write",
                    parent_uuid=None,
                    timestamp="2026-01-01T00:00:00Z",
                    tool_id="a-tool",
                    tool="Write",
                    tool_input={
                        "file_path": project_a_path,
                        "content": "project-a-value",
                    },
                    cwd="C:\\A",
                ),
                tool_result(
                    session_id="a",
                    uuid="a-result",
                    parent_uuid="a-write",
                    timestamp="2026-01-01T00:00:01Z",
                    assistant_uuid="a-write",
                    tool_id="a-tool",
                    content="created",
                    cwd="C:\\A",
                ),
            ],
            "b.jsonl": [
                assistant(
                    session_id="b",
                    uuid="b-write",
                    parent_uuid=None,
                    timestamp="2026-01-02T00:00:00Z",
                    tool_id="b-tool",
                    tool="Write",
                    tool_input={
                        "file_path": project_b_path,
                        "content": "project-b-value",
                    },
                    cwd="C:\\B",
                ),
                tool_result(
                    session_id="b",
                    uuid="b-result",
                    parent_uuid="b-write",
                    timestamp="2026-01-02T00:00:01Z",
                    assistant_uuid="b-write",
                    tool_id="b-tool",
                    content="created",
                    cwd="C:\\B",
                ),
            ],
            "c.jsonl": [
                assistant(
                    session_id="c",
                    uuid="c-read",
                    parent_uuid=None,
                    timestamp="2026-01-03T00:00:00Z",
                    tool_id="c-tool",
                    tool="Read",
                    tool_input={"file_path": project_a_path},
                    cwd="C:\\A",
                ),
                tool_result(
                    session_id="c",
                    uuid="c-result",
                    parent_uuid="c-read",
                    timestamp="2026-01-03T00:00:01Z",
                    assistant_uuid="c-read",
                    tool_id="c-tool",
                    content="1\tproject-a-value\n2\t",
                    cwd="C:\\A",
                ),
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sources = [
                write_source(root, name, records)
                for name, records in sources_by_name.items()
            ]
            manifest = write_manifest(root, sources)
            result = composition.analyze_manifest(manifest, root)

        self.assertEqual(2, result["discovery"]["apparent_projects"])
        self.assertEqual(
            1, result["discovery"]["multi_session_project_groups"]
        )
        self.assertEqual(
            {"numerator": 1, "denominator": 1, "rate": 1.0},
            result["mechanisms"]["contextual_bitemporal"]["online_exact"],
        )
        self.assertEqual(
            {"numerator": 0, "denominator": 1, "rate": 0.0},
            result["mechanisms"]["latest_only"]["online_exact"],
        )
        self.assertEqual(
            {"numerator": 1, "denominator": 1, "rate": 1.0},
            result["mechanisms"]["latest_only"][
                "online_cross_project_returns"
            ],
        )
        self.assertEqual(
            "failed",
            result["negative_controls"][
                "same_basename_different_project_placebo"
            ]["status"],
        )
        self.assertEqual(
            "passed",
            result["negative_controls"][
                "same_basename_different_project_placebo"
            ]["contextual_bitemporal"]["status"],
        )
        self.assertEqual(
            "failed",
            result["negative_controls"][
                "same_basename_different_project_placebo"
            ]["latest_only"]["status"],
        )
        self.assertEqual(
            1,
            result["negative_controls"][
                "same_basename_different_project_placebo"
            ]["latest_only"]["leaks"],
        )
        self.assertEqual(
            "failed",
            result["decision_status"]["latest_only_context_isolation"],
        )
        self.assertEqual(
            "passed",
            result["negative_controls"][
                "future_contaminated_positive_control"
            ]["status"],
        )
        self.assertEqual(
            "passed",
            result["negative_controls"]["future_filter"]["status"],
        )

    def test_overlapping_same_project_sessions_are_not_serial_evidence(self):
        first = [
            assistant(
                session_id="session-a",
                uuid="a-write",
                parent_uuid=None,
                timestamp="2026-01-01T00:00:00Z",
                tool_id="a-tool",
                tool="Write",
                tool_input={
                    "file_path": MEMORY_PATH,
                    "content": "observed value",
                },
            ),
            tool_result(
                session_id="session-a",
                uuid="a-result",
                parent_uuid="a-write",
                timestamp="2026-01-01T00:00:01Z",
                assistant_uuid="a-write",
                tool_id="a-tool",
                content="created",
            ),
            {
                "type": "system",
                "sessionId": "session-a",
                "uuid": "a-still-running",
                "parentUuid": "a-result",
                "timestamp": "2026-01-01T00:10:00Z",
                "cwd": "C:\\Research",
            },
        ]
        second = [
            assistant(
                session_id="session-b",
                uuid="b-read",
                parent_uuid=None,
                timestamp="2026-01-01T00:05:00Z",
                tool_id="b-tool",
                tool="Read",
                tool_input={"file_path": MEMORY_PATH},
            ),
            tool_result(
                session_id="session-b",
                uuid="b-result",
                parent_uuid="b-read",
                timestamp="2026-01-01T00:05:01Z",
                assistant_uuid="b-read",
                tool_id="b-tool",
                content="1\tobserved value\n2\t",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = write_manifest(
                root,
                [
                    write_source(root, "a.jsonl", first),
                    write_source(root, "b.jsonl", second),
                ],
            )
            result = composition.analyze_manifest(manifest, root)

        self.assertEqual(
            0, result["discovery"]["verified_serial_session_pairs"]
        )
        self.assertEqual(0, result["evaluation"]["online_queries"])
        self.assertEqual(
            0,
            result["evaluation"][
                "exact_cross_session_write_to_later_read"
            ],
        )

    def test_top_level_manifest_receipt_and_expected_inventory_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            nested_path = exact_write_read_fixture(root)
            nested = json.loads(nested_path.read_text(encoding="utf-8"))
            sources = nested["cohort"]["source_files"]
            top_level = {
                "schema_version": "trace-dataset-manifest-v1",
                "dataset_id": "synthetic/full-cohort",
                "dataset_revision": "fixture-v1",
                "license": "CC0-1.0",
                "adapter": "claude_native_context_transition_v1",
                "download_policy": {"raw_data_committed": False},
                "source_files": sources,
                "cohort_receipt_sha256": hashlib.sha256(
                    json.dumps(
                        sources,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "expected_inventory": {
                    "source_files": 2,
                    "records": 4,
                    "bytes": sum(item["bytes"] for item in sources),
                    "native_tool_calls": 2,
                    "native_tool_results": 2,
                    "apparent_projects": 1,
                    "multi_session_project_groups": 1,
                    "histories_with_context_artifact_interactions": 2,
                    "context_artifact_tool_interactions": 2,
                    "matching_tool_results": 2,
                    "explicit_reads": 1,
                    "writes_or_edits": 1,
                    "bash_search_or_other": 0,
                },
            }
            nested_path.write_text(
                json.dumps(top_level), encoding="utf-8"
            )
            result = composition.analyze_manifest(nested_path, root)
            self.assertEqual(
                top_level["cohort_receipt_sha256"],
                result["input_receipt"][
                    "manifest_cohort_receipt_sha256"
                ],
            )

            top_level["expected_inventory"]["explicit_reads"] = 2
            nested_path.write_text(
                json.dumps(top_level), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                composition.CompositionError, "explicit_reads"
            ):
                composition.analyze_manifest(nested_path, root)

    def test_classifier_ignores_content_and_counts_failed_or_unjoined_once(self):
        records = [
            assistant(
                session_id="session-a",
                uuid="a-notes",
                parent_uuid=None,
                timestamp="2026-01-01T00:00:00Z",
                tool_id="tool-notes",
                tool="Write",
                tool_input={
                    "file_path": "C:\\Research\\notes.txt",
                    "content": "mentions MEMORY.md but is not context",
                    "description": "edit MEMORY.md",
                },
            ),
            tool_result(
                session_id="session-a",
                uuid="u-notes",
                parent_uuid="a-notes",
                timestamp="2026-01-01T00:00:01Z",
                assistant_uuid="a-notes",
                tool_id="tool-notes",
                content="created",
            ),
            assistant(
                session_id="session-a",
                uuid="a-shell",
                parent_uuid="u-notes",
                timestamp="2026-01-01T00:01:00Z",
                tool_id="tool-shell",
                tool="Bash",
                tool_input={
                    "command": "echo safe",
                    "description": "read MEMORY.md",
                },
            ),
            tool_result(
                session_id="session-a",
                uuid="u-shell",
                parent_uuid="a-shell",
                timestamp="2026-01-01T00:01:01Z",
                assistant_uuid="a-shell",
                tool_id="tool-shell",
                content="safe",
            ),
            assistant(
                session_id="session-a",
                uuid="a-failed",
                parent_uuid="u-shell",
                timestamp="2026-01-01T00:02:00Z",
                tool_id="tool-failed",
                tool="Write",
                tool_input={
                    "file_path": MEMORY_PATH,
                    "content": "failed secret",
                },
            ),
            tool_result(
                session_id="session-a",
                uuid="u-failed",
                parent_uuid="a-failed",
                timestamp="2026-01-01T00:02:01Z",
                assistant_uuid="a-failed",
                tool_id="tool-failed",
                content="denied",
                is_error=True,
            ),
            assistant(
                session_id="session-a",
                uuid="a-unjoined",
                parent_uuid="u-failed",
                timestamp="2026-01-01T00:03:00Z",
                tool_id="tool-unjoined",
                tool="Write",
                tool_input={
                    "file_path": MEMORY_PATH,
                    "content": "missing result secret",
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = write_source(root, "session.jsonl", records)
            manifest = write_manifest(root, [source])
            result = composition.analyze_manifest(manifest, root)

        self.assertEqual(
            2, result["discovery"]["qualifying_candidate_calls"]
        )
        self.assertEqual(1, result["discovery"]["qualifying_interactions"])
        self.assertEqual(1, result["discovery"]["qualifying_failures"])
        self.assertEqual(
            1, result["discovery"]["qualifying_unmatched_calls"]
        )
        self.assertEqual(
            0, result["transitions"]["supported_observations"]
        )
        self.assertEqual(
            0, result["transitions"]["unique_supported_revisions"]
        )
        self.assertEqual(
            0,
            result["mechanisms"]["proposal_only_dream"][
                "automatically_active_changes"
            ],
        )

    def test_post_cutoff_gap_oracle_is_not_used_to_abstain(self):
        first = [
            assistant(
                session_id="session-a",
                uuid="a-write",
                parent_uuid=None,
                timestamp="2026-01-01T00:00:00Z",
                tool_id="a-tool",
                tool="Write",
                tool_input={
                    "file_path": MEMORY_PATH,
                    "content": "version one",
                },
            ),
            tool_result(
                session_id="session-a",
                uuid="a-result",
                parent_uuid="a-write",
                timestamp="2026-01-01T00:00:01Z",
                assistant_uuid="a-write",
                tool_id="a-tool",
                content="created",
            ),
        ]
        second = [
            assistant(
                session_id="session-b",
                uuid="b-read",
                parent_uuid=None,
                timestamp="2026-01-02T00:00:00Z",
                tool_id="b-tool",
                tool="Read",
                tool_input={"file_path": MEMORY_PATH},
            ),
            tool_result(
                session_id="session-b",
                uuid="b-result",
                parent_uuid="b-read",
                timestamp="2026-01-02T00:00:01Z",
                assistant_uuid="b-read",
                tool_id="b-tool",
                content="1\tversion two\n2\t",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sources = [
                write_source(root, "session-a.jsonl", first),
                write_source(root, "session-b.jsonl", second),
            ]
            manifest = write_manifest(root, sources)
            result = composition.analyze_manifest(manifest, root)

        for arm in ("verbatim", "latest_only", "contextual_bitemporal"):
            self.assertEqual(
                {"numerator": 1, "denominator": 1, "rate": 1.0},
                result["mechanisms"][arm]["online_stale_returns"],
            )
            self.assertEqual(
                {"numerator": 0, "denominator": 1, "rate": 0.0},
                result["mechanisms"][arm]["online_abstentions"],
            )
        self.assertEqual(
            1, result["transitions"]["interval_censored_changes"]
        )

    def test_deterministic_contract_mutation_is_rejected(self):
        source_manifest = (
            ROOT
            / "configs"
            / "datasets"
            / "trace-commons-memory-full-cohort.json"
        )
        source_config = (
            ROOT
            / "configs"
            / "experiments"
            / "trace-commons-memory-composition-2026.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            dataset_dir = root / "configs" / "datasets"
            experiment_dir = root / "configs" / "experiments"
            dataset_dir.mkdir(parents=True)
            experiment_dir.mkdir(parents=True)
            manifest = dataset_dir / source_manifest.name
            config_path = experiment_dir / source_config.name
            manifest.write_bytes(source_manifest.read_bytes())
            config = json.loads(source_config.read_text(encoding="utf-8"))
            config_path.write_text(json.dumps(config), encoding="utf-8")
            loaded, receipt = composition._load_experiment_config(
                config_path, manifest
            )
            self.assertEqual(
                "enabled",
                loaded["phase_status"][
                    "deterministic_mechanics_preflight"
                ],
            )
            self.assertEqual(64, len(receipt))

            config["common_state_reducer"]["procedure"] = []
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(
                composition.CompositionError,
                "deterministic experiment contract mismatch",
            ):
                composition._load_experiment_config(config_path, manifest)

    def test_same_length_source_mutation_is_rejected_before_composition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = exact_write_read_fixture(root)
            source = root / "session-a.jsonl"
            raw = source.read_bytes()
            replacement = b"X" * len(SECRET.encode("utf-8"))
            mutated = raw.replace(SECRET.encode("utf-8"), replacement)
            self.assertEqual(len(raw), len(mutated))
            source.write_bytes(mutated)

            with self.assertRaisesRegex(
                native.ConformanceError,
                "SHA-256 does not match",
            ):
                composition.analyze_manifest(manifest, root)


if __name__ == "__main__":
    unittest.main()
