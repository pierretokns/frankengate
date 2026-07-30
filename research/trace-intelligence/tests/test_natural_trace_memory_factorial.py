import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import natural_trace_memory_factorial as natural  # noqa: E402


MEMORY_PATH = "/work/.claude/projects/example/memory/MEMORY.md"
SECRET_ALPHA = "private natural state alpha"
SECRET_BETA = "private natural state beta"


def assistant(
    *,
    session_id,
    uuid,
    parent_uuid,
    timestamp,
    tool_id,
    tool,
    tool_input,
    cwd="/work/example",
):
    return {
        "type": "assistant",
        "sessionId": session_id,
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_id,
                    "name": tool,
                    "input": tool_input,
                }
            ],
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
    cwd="/work/example",
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
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": content,
                    "is_error": is_error,
                }
            ],
        },
    }


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def source_fixture(root):
    source_root = root / "source"
    manifest = {
        "schema_version": "trace-dataset-manifest-v1",
        "dataset_id": "test/natural-memory",
        "dataset_revision": "revision-1",
        "license": "CC0-1.0",
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    write_jsonl(
        source_root / "project-a" / "session-write.jsonl",
        [
            assistant(
                session_id="write",
                uuid="write-call",
                parent_uuid=None,
                timestamp="2026-01-01T00:00:00Z",
                tool_id="write-tool",
                tool="Write",
                tool_input={
                    "file_path": MEMORY_PATH,
                    "content": SECRET_ALPHA,
                },
            ),
            tool_result(
                session_id="write",
                uuid="write-result",
                parent_uuid="write-call",
                timestamp="2026-01-01T00:00:01Z",
                assistant_uuid="write-call",
                tool_id="write-tool",
                content="created",
            ),
        ],
    )
    write_jsonl(
        source_root / "project-a" / "session-read.jsonl",
        [
            assistant(
                session_id="read",
                uuid="read-call",
                parent_uuid=None,
                timestamp="2026-01-02T00:00:00Z",
                tool_id="read-tool",
                tool="Read",
                tool_input={"file_path": MEMORY_PATH},
            ),
            tool_result(
                session_id="read",
                uuid="read-result",
                parent_uuid="read-call",
                timestamp="2026-01-02T00:00:01Z",
                assistant_uuid="read-call",
                tool_id="read-tool",
                content=f"1\t{SECRET_ALPHA}\n2\t",
            ),
        ],
    )
    # A same-named artifact in a different project must never become evidence
    # for project-a. Its only read occurs before its write and is ineligible.
    write_jsonl(
        source_root / "project-b" / "session-future.jsonl",
        [
            assistant(
                session_id="future",
                uuid="early-read-call",
                parent_uuid=None,
                timestamp="2026-01-03T00:00:00Z",
                tool_id="early-read-tool",
                tool="Read",
                tool_input={"file_path": MEMORY_PATH},
            ),
            tool_result(
                session_id="future",
                uuid="early-read-result",
                parent_uuid="early-read-call",
                timestamp="2026-01-03T00:00:01Z",
                assistant_uuid="early-read-call",
                tool_id="early-read-tool",
                content=f"1\t{SECRET_BETA}\n2\t",
            ),
            assistant(
                session_id="future",
                uuid="future-write-call",
                parent_uuid="early-read-result",
                timestamp="2026-01-03T00:00:02Z",
                tool_id="future-write-tool",
                tool="Write",
                tool_input={
                    "file_path": MEMORY_PATH,
                    "content": SECRET_BETA,
                },
            ),
            tool_result(
                session_id="future",
                uuid="future-write-result",
                parent_uuid="future-write-call",
                timestamp="2026-01-03T00:00:03Z",
                assistant_uuid="future-write-call",
                tool_id="future-write-tool",
                content="created",
            ),
        ],
    )
    return natural.SourceSpec(
        label="fixture",
        root=source_root,
        manifest=manifest_path,
    )


class NaturalTraceMemoryFactorialTest(unittest.TestCase):
    def test_protocol_config_binds_corrected_parent_and_factorial(self):
        config = (
            ROOT
            / "configs"
            / "experiments"
            / "natural-trace-memory-factorial-v1-2026.json"
        )

        receipt = natural.load_protocol_config(config)

        self.assertEqual(
            hashlib.sha256(config.read_bytes()).hexdigest(),
            receipt["protocol_config_sha256"],
        )
        self.assertEqual(
            "b4f3643a9439481e3e10ede38c9c3ac420a3f5112bb893b9910e470bca67ef0c",
            receipt["inherited_protocol_sha256"],
        )
        self.assertEqual(16, receipt["expected_arms"])
        self.assertEqual(
            ["fable5", "wisp"],
            sorted(
                item["label"]
                for item in receipt["source_bindings"]
            ),
        )

    def test_bound_protocol_rejects_an_unlisted_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = source_fixture(Path(tmp))
            with self.assertRaises(natural.NaturalMemoryError):
                natural.analyze_sources(
                    [source],
                    identity_key=b"k" * 32,
                    protocol_receipt={
                        "source_bindings": [],
                        "expected_arms": 16,
                    },
                )

    def test_natural_read_outcome_uses_only_same_project_prequery_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = natural.analyze_sources(
                [source_fixture(Path(tmp))],
                identity_key=b"k" * 32,
            )

        self.assertEqual(1, result["design"]["eligible_queries"])
        self.assertEqual(1, result["discovery"]["cross_session_queries"])
        by_mechanisms = {
            tuple(arm["mechanisms"]): arm for arm in result["arms"]
        }
        self.assertEqual(1, by_mechanisms[("latest_snapshot",)]["exact"])
        self.assertEqual(1, by_mechanisms[("verbatim_state",)]["exact"])
        self.assertEqual(1, by_mechanisms[("bitemporal_ledger",)]["exact"])
        self.assertEqual(1, by_mechanisms[("evidence_retrieval",)]["exact"])
        self.assertEqual(1, by_mechanisms[()]["abstention"])
        self.assertEqual(
            1,
            result["gates"]["excluded_reads_without_prequery_evidence"],
        )
        self.assertEqual(0, result["audit"]["post_query_items_supplied"])
        self.assertEqual(0, result["audit"]["cross_project_items_supplied"])

    def test_overlapping_session_is_not_treated_as_serial_memory_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = source_fixture(Path(tmp))
            read_path = (
                source.root / "project-a" / "session-read.jsonl"
            )
            records = [
                json.loads(line)
                for line in read_path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            records[0]["timestamp"] = "2026-01-01T00:00:00.500Z"
            records[1]["timestamp"] = "2026-01-01T00:00:00.750Z"
            write_jsonl(read_path, records)

            result = natural.analyze_sources(
                [source],
                identity_key=b"k" * 32,
            )

        self.assertEqual(0, result["design"]["eligible_queries"])
        self.assertEqual(
            2,
            result["gates"]["excluded_reads_without_prequery_evidence"],
        )
        self.assertEqual(0, result["discovery"]["cross_session_queries"])

    def test_sibling_branch_state_is_not_supplied_to_target_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "source"
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "trace-dataset-manifest-v1",
                        "dataset_id": "test/branch",
                        "dataset_revision": "revision-1",
                        "license": "CC0-1.0",
                    }
                ),
                encoding="utf-8",
            )
            write_jsonl(
                source_root / "project-a" / "branched.jsonl",
                [
                    assistant(
                        session_id="branched",
                        uuid="write-call",
                        parent_uuid=None,
                        timestamp="2026-01-01T00:00:00Z",
                        tool_id="write-tool",
                        tool="Write",
                        tool_input={
                            "file_path": MEMORY_PATH,
                            "content": SECRET_ALPHA,
                        },
                    ),
                    tool_result(
                        session_id="branched",
                        uuid="write-result",
                        parent_uuid="write-call",
                        timestamp="2026-01-01T00:00:01Z",
                        assistant_uuid="write-call",
                        tool_id="write-tool",
                        content="created",
                    ),
                    assistant(
                        session_id="branched",
                        uuid="read-call",
                        parent_uuid=None,
                        timestamp="2026-01-01T00:00:02Z",
                        tool_id="read-tool",
                        tool="Read",
                        tool_input={"file_path": MEMORY_PATH},
                    ),
                    tool_result(
                        session_id="branched",
                        uuid="read-result",
                        parent_uuid="read-call",
                        timestamp="2026-01-01T00:00:03Z",
                        assistant_uuid="read-call",
                        tool_id="read-tool",
                        content=f"1\t{SECRET_ALPHA}\n2\t",
                    ),
                ],
            )
            result = natural.analyze_sources(
                [
                    natural.SourceSpec(
                        label="branch",
                        root=source_root,
                        manifest=manifest_path,
                    )
                ],
                identity_key=b"k" * 32,
            )

        self.assertEqual(0, result["design"]["eligible_queries"])
        self.assertEqual(
            1,
            result["gates"]["excluded_reads_without_prequery_evidence"],
        )

    def test_supported_factorial_and_unsupported_natural_release_gates_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = natural.analyze_sources(
                [source_fixture(Path(tmp))],
                identity_key=b"k" * 32,
            )

        self.assertEqual(
            [
                "latest_snapshot",
                "verbatim_state",
                "bitemporal_ledger",
                "evidence_retrieval",
            ],
            result["design"]["runnable_mechanisms"],
        )
        self.assertEqual(16, result["design"]["arm_count"])
        self.assertEqual(1, result["design"]["zero_mechanism_arms"])
        self.assertEqual(4, result["design"]["single_mechanism_arms"])
        self.assertEqual(11, result["design"]["composed_arms"])
        self.assertEqual(
            "not_runnable_no_natural_independent_release",
            result["mechanism_gates"]["released_dream"]["status"],
        )
        self.assertEqual(
            "not_runnable_no_natural_independent_release",
            result["mechanism_gates"]["released_procedure"]["status"],
        )
        self.assertEqual(
            0,
            result["mechanism_gates"]["released_dream"][
                "independently_released_items"
            ],
        )
        self.assertEqual(
            0,
            result["mechanism_gates"]["released_procedure"][
                "independently_released_items"
            ],
        )
        self.assertEqual(
            1,
            result["treatment_contrast_gate"][
                "distinct_runnable_singleton_outcome_vectors"
            ],
        )
        self.assertEqual(
            0,
            result["treatment_contrast_gate"][
                "runnable_singleton_pairwise_decision_differences"
            ],
        )
        self.assertFalse(
            result["treatment_contrast_gate"][
                "differential_mechanism_effect_identifiable"
            ]
        )

    def test_durable_result_is_aggregate_only_and_split_without_project_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = natural.analyze_sources(
                [source_fixture(Path(tmp))],
                identity_key=b"k" * 32,
            )

        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(SECRET_ALPHA, serialized)
        self.assertNotIn(SECRET_BETA, serialized)
        self.assertNotIn(MEMORY_PATH, serialized)
        self.assertNotIn("project-a", serialized)
        self.assertNotIn("project-b", serialized)
        self.assertEqual(
            {"source", "project", "target_time"},
            set(result["splits"]),
        )
        self.assertEqual(
            [1],
            result["splits"]["project"]["eligible_queries_per_project_desc"],
        )
        self.assertTrue(result["content_policy"]["raw_content_emitted"] is False)
        self.assertTrue(result["content_policy"]["native_identifiers_emitted"] is False)
        self.assertTrue(natural.verify_result(result))

    def test_result_receipt_changes_when_source_bytes_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture_root = Path(tmp)
            source = source_fixture(fixture_root)
            first = natural.analyze_sources(
                [source],
                identity_key=b"k" * 32,
            )
            path = source.root / "project-a" / "session-read.jsonl"
            path.write_bytes(path.read_bytes() + b"\n")
            second = natural.analyze_sources(
                [source],
                identity_key=b"k" * 32,
            )

        self.assertNotEqual(
            first["input_receipts"][0]["source_set_sha256"],
            second["input_receipts"][0]["source_set_sha256"],
        )
        self.assertNotEqual(first["result_sha256"], second["result_sha256"])


if __name__ == "__main__":
    unittest.main()
