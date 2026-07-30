import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from canonical_projection_e0 import (  # noqa: E402
    E0_RECEIPT_VERSION,
    ProjectionValidationError,
    canonical_to_atif_e0,
    canonical_to_openinference_otel,
    openinference_otel_to_canonical,
    run_conformance,
    verify_projection_receipt,
)


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def event(event_id, sequence, kind, role, content=None, **fields):
    return {
        "event_id": event_id,
        "sequence": sequence,
        "kind": kind,
        "observation_status": "observed",
        "source_role": role,
        "content": content,
        **fields,
    }


def canonical(events, **fields):
    return {
        "schema_version": "canonical-trajectory-v1",
        "trace_id": sha("e0-fixture"),
        "source": {
            "dataset_id": "synthetic/e0",
            "dataset_revision": "1",
            "adapter": "synthetic-e0-v1",
        },
        "task": {"task_id": "synthetic"},
        "events": events,
        "outcome": {"value": "synthetic", "source": "fixture"},
        "loss_receipt": {
            "source_event_count": len(events),
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
            "reconstructed_fields": [],
            "known_missing_fields": [],
        },
        **fields,
    }


class CanonicalProjectionE0Test(unittest.TestCase):
    def test_parallel_dag_projects_to_parents_and_links(self):
        source = canonical(
            [
                event("root", 0, "branch_fork", "orchestrator", "fork"),
                event(
                    "left",
                    1,
                    "branch_result",
                    "agent",
                    "left",
                    parent_event_id="root",
                    branch_id="left",
                ),
                event(
                    "right",
                    2,
                    "branch_result",
                    "agent",
                    "right",
                    parent_event_id="root",
                    branch_id="right",
                ),
                event(
                    "join",
                    3,
                    "branch_join",
                    "orchestrator",
                    "join",
                    parent_event_id="root",
                    predecessor_event_ids=["left", "right"],
                ),
            ]
        )

        projection, receipt = canonical_to_openinference_otel(source)
        imported, import_receipt = openinference_otel_to_canonical(projection)

        by_id = {item["event_id"]: item for item in imported["events"]}
        self.assertEqual("root", by_id["join"]["parent_event_id"])
        self.assertEqual(
            ["left", "right"], by_id["join"]["predecessor_event_ids"]
        )
        self.assertEqual(4, len(imported["events"]))
        self.assertEqual(0, import_receipt["silently_dropped_event_count"])
        self.assertTrue(receipt["capability_summary"]["dag"]["present"])
        self.assertTrue(
            receipt["capability_summary"]["parallelism"]["present"]
        )
        verify_projection_receipt(source, projection, receipt)

    def test_authority_environment_evaluation_and_replay_are_explicit(self):
        source = canonical(
            [
                event(
                    "auth",
                    0,
                    "authorization_decision",
                    "governance",
                    "SECRET AUTH CONTENT",
                    authorization_epoch=9,
                    subject_id="SECRET USER",
                    classification="restricted",
                ),
                event(
                    "state",
                    1,
                    "state_delta",
                    "environment",
                    "SECRET STATE",
                    parent_event_id="auth",
                    before_digest="sha256:before",
                    after_digest="sha256:after",
                    checkpoint_ref="SECRET CHECKPOINT",
                ),
                event(
                    "score",
                    2,
                    "evaluation.recorded",
                    "evaluator",
                    "SECRET SCORE",
                    parent_event_id="state",
                    reward_total=1.0,
                ),
            ],
            authorization_epoch=9,
            classification="restricted",
            replay={"snapshot_ref": "SECRET SNAPSHOT"},
        )

        atif, atif_receipt = canonical_to_atif_e0(source)
        otel, otel_receipt = canonical_to_openinference_otel(source)

        for receipt in (atif_receipt, otel_receipt):
            for capability in (
                "dag",
                "authorization",
                "environment",
                "evaluation",
                "replay",
            ):
                summary = receipt["capability_summary"][capability]
                self.assertTrue(summary["present"], capability)
                self.assertEqual(
                    summary["source_field_count"],
                    summary["receipted_field_count"],
                )
        encoded_otel = json.dumps(otel)
        self.assertNotIn("SECRET AUTH CONTENT", encoded_otel)
        self.assertNotIn("SECRET USER", encoded_otel)
        self.assertNotIn("SECRET STATE", encoded_otel)
        self.assertNotIn("SECRET SCORE", encoded_otel)
        self.assertNotIn("SECRET CHECKPOINT", encoded_otel)
        self.assertNotIn("SECRET SNAPSHOT", encoded_otel)
        encoded_atif = json.dumps(atif)
        self.assertNotIn("SECRET AUTH CONTENT", encoded_atif)
        self.assertNotIn("SECRET STATE", encoded_atif)
        self.assertNotIn("SECRET SCORE", encoded_atif)
        self.assertGreater(
            atif_receipt["item_category_counts"]["redacted"], 0
        )

    def test_tool_lifecycle_and_out_of_order_results_remain_correlated(self):
        source = canonical(
            [
                event("m", 0, "conversation.message", "agent", "parallel"),
                event(
                    "pa",
                    1,
                    "tool.proposed",
                    "agent",
                    parent_event_id="m",
                    tool_call_id="a",
                    function_name="lookup",
                    arguments={"q": "private"},
                ),
                event(
                    "pb",
                    2,
                    "tool.proposed",
                    "agent",
                    parent_event_id="m",
                    tool_call_id="b",
                    function_name="lookup",
                    arguments={"q": "private"},
                ),
                event(
                    "rb",
                    3,
                    "tool.completed",
                    "tool",
                    "private-b",
                    parent_event_id="pb",
                    tool_call_id="b",
                ),
                event(
                    "ra",
                    4,
                    "tool.completed",
                    "tool",
                    "private-a",
                    parent_event_id="pa",
                    tool_call_id="a",
                ),
            ]
        )

        projection, receipt = canonical_to_openinference_otel(source)
        imported, _ = openinference_otel_to_canonical(projection)
        by_id = {item["event_id"]: item for item in imported["events"]}

        self.assertEqual("b", by_id["rb"]["tool_call_id"])
        self.assertEqual("pb", by_id["rb"]["parent_event_id"])
        self.assertEqual("a", by_id["ra"]["tool_call_id"])
        self.assertEqual("pa", by_id["ra"]["parent_event_id"])
        self.assertNotIn("private-a", json.dumps(projection))
        self.assertGreater(receipt["item_category_counts"]["redacted"], 0)

    def test_receipt_detects_source_and_projection_mutation(self):
        source = canonical(
            [event("one", 0, "conversation.message", "user", "content")]
        )
        projection, receipt = canonical_to_openinference_otel(source)

        mutated_source = copy.deepcopy(source)
        mutated_source["events"][0]["kind"] = "model.completed"
        with self.assertRaisesRegex(
            ProjectionValidationError, "source mutation"
        ):
            verify_projection_receipt(mutated_source, projection, receipt)

        mutated_projection = copy.deepcopy(projection)
        mutated_projection["otlp"]["resourceSpans"][0]["scopeSpans"][0][
            "spans"
        ][0]["name"] = "mutated"
        with self.assertRaisesRegex(
            ProjectionValidationError, "projection mutation"
        ):
            verify_projection_receipt(source, mutated_projection, receipt)

    def test_input_immutability_determinism_and_invalid_source(self):
        source = canonical(
            [
                event("two", 2, "conversation.message", "agent", "two"),
                event("one", 1, "conversation.message", "user", "one"),
            ]
        )
        before = copy.deepcopy(source)
        first = canonical_to_openinference_otel(source)
        second = canonical_to_openinference_otel(source)
        self.assertEqual(first, second)
        self.assertEqual(before, source)

        invalid = copy.deepcopy(source)
        invalid["events"][1]["event_id"] = "two"
        with self.assertRaisesRegex(
            ProjectionValidationError, "duplicate canonical event_id"
        ):
            canonical_to_openinference_otel(invalid)

    def test_atif_wrapper_retains_native_receipt_and_hashes(self):
        source = canonical(
            [
                event(
                    "x",
                    0,
                    "provider.retry",
                    "gateway",
                    "retry",
                    parent_event_id="missing",
                    replay_level="R1",
                )
            ]
        )
        projection, receipt = canonical_to_atif_e0(source)

        self.assertEqual(E0_RECEIPT_VERSION, receipt["schema_version"])
        self.assertIn("native_receipt_id", receipt)
        self.assertEqual(
            receipt["native_receipt_id"],
            receipt["native_receipt"]["receipt_id"],
        )
        self.assertEqual(0, receipt["silently_dropped_event_count"])
        self.assertEqual(1, receipt["accounted_source_event_count"])
        verify_projection_receipt(source, projection, receipt)
        mutated = copy.deepcopy(projection)
        mutated["agent"]["name"] = "mutated"
        with self.assertRaisesRegex(
            ProjectionValidationError, "projection mutation"
        ):
            verify_projection_receipt(source, mutated, receipt)

    def test_aggregate_conformance_result_emits_no_fixture_content_or_ids(self):
        source = canonical(
            [
                event(
                    "SECRET-EVENT-ID",
                    0,
                    "authorization_decision",
                    "governance",
                    "SECRET CONTENT",
                    subject_id="SECRET USER",
                )
            ]
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "fixture.json").write_text(json.dumps(source))
            result = run_conformance(root)

        serialized = json.dumps(result)
        self.assertNotIn("SECRET-EVENT-ID", serialized)
        self.assertNotIn("SECRET CONTENT", serialized)
        self.assertNotIn("SECRET USER", serialized)
        self.assertEqual(1.0, result["OpenInference_OTel"][
            "canonical_event_identity_retention"
        ])

    def test_receipt_schema_requires_hashes_and_zero_silent_drop(self):
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "canonical-projection-loss-receipt.schema.json"
            ).read_text()
        )
        required = set(schema["required"])
        self.assertIn("source_sha256", required)
        self.assertIn("projection_sha256", required)
        self.assertEqual(
            0,
            schema["properties"]["silently_dropped_event_count"]["const"],
        )


if __name__ == "__main__":
    unittest.main()
