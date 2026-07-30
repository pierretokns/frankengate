import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from atif_adapter import (  # noqa: E402
    ATIFValidationError,
    assert_no_silent_loss,
    atif_to_canonical,
    canonical_to_atif,
    stable_round_trip,
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


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


def canonical(events):
    return {
        "schema_version": "canonical-trajectory-v1",
        "trace_id": sha("trace"),
        "source": {
            "dataset_id": "fixture",
            "dataset_revision": "1",
            "adapter": "fixture",
            "agent": {"name": "fixture-agent", "version": "1.2.3"},
        },
        "task": {"task_id": "task-1"},
        "events": events,
        "outcome": {"value": "success", "source": "fixture"},
        "loss_receipt": {
            "source_event_count": len(events),
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
            "reconstructed_fields": [],
            "known_missing_fields": [],
        },
    }


def minimal_atif():
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": "run-1",
        "trajectory_id": "trajectory-1",
        "agent": {"name": "agent", "version": "1"},
        "steps": [
            {
                "step_id": 1,
                "source": "agent",
                "message": "I will inspect it.",
                "llm_call_count": 1,
                "tool_calls": [
                    {
                        "tool_call_id": "call-1",
                        "function_name": "inspect",
                        "arguments": {"path": "README.md"},
                    }
                ],
                "observation": {
                    "results": [{"source_call_id": "call-1", "content": "ok"}]
                },
            }
        ],
    }


class CanonicalToATIFTests(unittest.TestCase):
    def test_native_tool_proposal_call_result_lifecycle(self):
        source = canonical(
            [
                event("m1", 0, "conversation.message", "agent", "Checking."),
                event(
                    "p1",
                    1,
                    "tool.proposed",
                    "agent",
                    parent_event_id="m1",
                    tool_call_id="c1",
                    function_name="lookup",
                    arguments={"q": "alpha"},
                ),
                event(
                    "s1",
                    2,
                    "tool.started",
                    "tool",
                    parent_event_id="p1",
                    tool_call_id="c1",
                    started_at="2026-07-30T12:00:00Z",
                ),
                event(
                    "r1",
                    3,
                    "tool.completed",
                    "tool",
                    "found",
                    parent_event_id="p1",
                    tool_call_id="c1",
                    status="success",
                    ended_at="2026-07-30T12:00:01Z",
                ),
            ]
        )
        atif, receipt = canonical_to_atif(source)
        self.assertEqual(atif["steps"][0]["tool_calls"][0]["tool_call_id"], "c1")
        self.assertEqual(
            atif["steps"][0]["observation"]["results"][0]["source_call_id"], "c1"
        )
        # ATIF cannot express the started event; it is named and hashed.
        manifests = receipt["unprojected_event_manifests"]
        self.assertEqual([item["event_id"] for item in manifests], ["s1"])
        self.assertEqual(receipt["accounted_source_event_count"], 4)
        assert_no_silent_loss(receipt)

    def test_missing_tool_result_is_not_fabricated(self):
        source = canonical(
            [
                event("m1", 0, "conversation.message", "agent", "Calling."),
                event(
                    "p1",
                    1,
                    "tool.proposed",
                    "agent",
                    parent_event_id="m1",
                    tool_call_id="c1",
                    function_name="lookup",
                    arguments={},
                ),
            ]
        )
        atif, receipt = canonical_to_atif(source)
        self.assertNotIn("observation", atif["steps"][0])
        self.assertFalse(
            any("synthetic ToolCall" in item["reason"] for item in receipt["items"])
        )
        assert_no_silent_loss(receipt)

    def test_orphan_tool_proposal_gets_distinct_reconstructed_dispatch(self):
        source = canonical(
            [
                event(
                    "p1",
                    0,
                    "tool.proposed",
                    "agent",
                    tool_call_id="c1",
                    function_name="lookup",
                    arguments={},
                )
            ]
        )
        atif, receipt = canonical_to_atif(source)
        imported, import_receipt = atif_to_canonical(atif)
        self.assertEqual(
            [item["event_id"] for item in imported["events"]],
            ["synthetic-dispatch-for-p1", "p1"],
        )
        self.assertEqual(
            [item["kind"] for item in imported["events"]],
            ["conversation.message", "tool.proposed"],
        )
        self.assertEqual(len({item["event_id"] for item in imported["events"]}), 2)
        assert_no_silent_loss(receipt)
        assert_no_silent_loss(import_receipt)

    def test_result_without_proposal_is_explicitly_reconstructed(self):
        source = canonical(
            [
                event(
                    "r1",
                    0,
                    "tool.completed",
                    "tool",
                    "orphan",
                    tool_call_id="missing-call",
                )
            ]
        )
        atif, receipt = canonical_to_atif(source)
        self.assertEqual(
            atif["steps"][0]["tool_calls"][0]["tool_call_id"], "missing-call"
        )
        self.assertTrue(
            any(item["category"] == "reconstructed" for item in receipt["items"])
        )
        imported, import_receipt = atif_to_canonical(atif)
        # The result remains one source event; the importer also makes the two
        # reconstructions (agent dispatch and proposal) explicit.
        self.assertEqual(len({item["event_id"] for item in imported["events"]}), 3)
        assert_no_silent_loss(receipt)
        assert_no_silent_loss(import_receipt)

    def test_repeated_call_id_retry_is_made_unique_but_original_is_restored(self):
        source = canonical(
            [
                event("m1", 0, "conversation.message", "agent", "Retrying."),
                event(
                    "p1",
                    1,
                    "tool.proposed",
                    "agent",
                    parent_event_id="m1",
                    tool_call_id="same",
                    function_name="fetch",
                    arguments={},
                    attempt=1,
                ),
                event(
                    "f1",
                    2,
                    "tool.failed",
                    "tool",
                    "timeout",
                    tool_call_id="same",
                    attempt=1,
                    status="error",
                ),
                event(
                    "p2",
                    3,
                    "tool.proposed",
                    "agent",
                    parent_event_id="m1",
                    tool_call_id="same",
                    function_name="fetch",
                    arguments={},
                    attempt=2,
                ),
                event(
                    "r2",
                    4,
                    "tool.completed",
                    "tool",
                    "ok",
                    tool_call_id="same",
                    attempt=2,
                    status="success",
                ),
            ]
        )
        atif, receipt = canonical_to_atif(source)
        call_ids = [item["tool_call_id"] for item in atif["steps"][0]["tool_calls"]]
        self.assertEqual(call_ids, ["same", "same__attempt_2"])
        result_ids = [
            item["source_call_id"]
            for item in atif["steps"][0]["observation"]["results"]
        ]
        self.assertEqual(result_ids, ["same", "same__attempt_2"])
        imported, _ = atif_to_canonical(atif)
        imported_calls = [
            item["tool_call_id"]
            for item in imported["events"]
            if item["kind"].startswith("tool.")
        ]
        self.assertEqual(set(imported_calls), {"same"})
        self.assertTrue(
            any("made unique" in item["reason"] for item in receipt["items"])
        )
        assert_no_silent_loss(receipt)

    def test_parallel_calls_and_out_of_order_results_remain_correlated(self):
        source = canonical(
            [
                event("m1", 0, "conversation.message", "agent", "Parallel."),
                event(
                    "pa",
                    1,
                    "tool.proposed",
                    "agent",
                    parent_event_id="m1",
                    tool_call_id="a",
                    function_name="a",
                    arguments={},
                ),
                event(
                    "pb",
                    2,
                    "tool.proposed",
                    "agent",
                    parent_event_id="m1",
                    tool_call_id="b",
                    function_name="b",
                    arguments={},
                ),
                event("rb", 3, "tool.completed", "tool", "B", tool_call_id="b"),
                event("ra", 4, "tool.completed", "tool", "A", tool_call_id="a"),
            ]
        )
        atif, receipt = canonical_to_atif(source)
        results = atif["steps"][0]["observation"]["results"]
        self.assertEqual([item["source_call_id"] for item in results], ["b", "a"])
        self.assertEqual([item["content"] for item in results], ["B", "A"])
        assert_no_silent_loss(receipt)

    def test_branch_and_delegation_are_receipted_as_nonportable(self):
        source = canonical(
            [
                event("m1", 0, "conversation.message", "agent", "Delegate."),
                event(
                    "d1",
                    1,
                    "delegation.started",
                    "agent",
                    parent_event_id="m1",
                    caused_by_event_id="m1",
                    linked_event_ids=["peer"],
                    branch_id="branch-a",
                    delegation_id="delegation-a",
                ),
                event(
                    "d2",
                    2,
                    "delegation.completed",
                    "agent",
                    parent_event_id="d1",
                    branch_id="branch-a",
                    delegation_id="delegation-a",
                ),
            ]
        )
        atif, receipt = canonical_to_atif(source)
        manifests = atif["extra"]["frankengate"]["unprojected_event_manifests"]
        self.assertEqual({item["event_id"] for item in manifests}, {"d1", "d2"})
        paths = {item["path"] for item in receipt["items"]}
        self.assertIn("events[d1].linked_event_ids", paths)
        self.assertIn("events[d1].delegation_id", paths)
        self.assertIn("events[d2].parent_event_id", paths)
        assert_no_silent_loss(receipt)

    def test_environment_and_reward_are_extension_only_and_receipted(self):
        source = canonical(
            [
                event("m1", 0, "conversation.message", "agent", "Act."),
                event(
                    "env1",
                    1,
                    "environment.transitioned",
                    "environment",
                    parent_event_id="m1",
                    state_before_ref="sha256:before",
                    state_after_ref="sha256:after",
                ),
                event(
                    "reward1",
                    2,
                    "evaluation.recorded",
                    "evaluator",
                    parent_event_id="m1",
                    reward_total=0.75,
                    reward_components={"correct": 1.0, "cost": -0.25},
                ),
            ]
        )
        atif, receipt = canonical_to_atif(source)
        ext_events = atif["steps"][0]["extra"]["frankengate"][
            "environment_and_reward_events"
        ]
        self.assertEqual([item["event_id"] for item in ext_events], ["env1", "reward1"])
        unsupported_ids = {
            item.get("event_id")
            for item in receipt["items"]
            if item["category"] == "unsupported"
        }
        self.assertTrue({"env1", "reward1"}.issubset(unsupported_ids))
        imported, import_receipt = atif_to_canonical(atif)
        self.assertEqual(
            {item["kind"] for item in imported["events"]},
            {"conversation.message", "environment.transitioned", "evaluation.recorded"},
        )
        assert_no_silent_loss(receipt)
        assert_no_silent_loss(import_receipt)

    def test_redaction_and_sensitive_extension_filtering(self):
        source = canonical(
            [
                event(
                    "m1",
                    0,
                    "conversation.message",
                    "user",
                    "top secret",
                    redacted=True,
                    redaction_revision="r2",
                    token="must-not-leak",
                    api_key="must-not-leak",
                    harmless="kept",
                )
            ]
        )
        atif, receipt = canonical_to_atif(source)
        self.assertEqual(atif["steps"][0]["message"], "[REDACTED]")
        encoded = json.dumps(atif)
        self.assertNotIn("must-not-leak", encoded)
        metadata = atif["steps"][0]["extra"]["frankengate"]["canonical_metadata"]
        self.assertEqual(metadata["harmless"], "kept")
        self.assertTrue(any(item["category"] == "redacted" for item in receipt["items"]))
        assert_no_silent_loss(receipt)

    def test_unknown_event_is_manifested_not_silently_dropped(self):
        source = canonical(
            [event("x1", 0, "provider.unreleased.future.event", "provider", {"x": 1})]
        )
        atif, receipt = canonical_to_atif(source)
        self.assertEqual(receipt["source_event_count"], 1)
        self.assertEqual(receipt["accounted_source_event_count"], 1)
        self.assertEqual(
            receipt["unprojected_event_manifests"][0]["event_id"], "x1"
        )
        self.assertEqual(receipt["silently_dropped_event_count"], 0)
        assert_no_silent_loss(receipt)


class ATIFToCanonicalTests(unittest.TestCase):
    def test_import_tool_lifecycle_and_missing_result(self):
        atif = minimal_atif()
        atif["steps"][0]["tool_calls"].append(
            {
                "tool_call_id": "call-without-result",
                "function_name": "noop",
                "arguments": {},
            }
        )
        canonical_doc, receipt = atif_to_canonical(atif)
        kinds = [item["kind"] for item in canonical_doc["events"]]
        self.assertEqual(
            kinds, ["conversation.message", "tool.proposed", "tool.proposed", "tool.completed"]
        )
        missing = [
            item
            for item in canonical_doc["events"]
            if item.get("tool_call_id") == "call-without-result"
        ]
        self.assertEqual([item["kind"] for item in missing], ["tool.proposed"])
        assert_no_silent_loss(receipt)

    def test_unknown_message_part_and_source_are_preserved_with_receipt(self):
        atif = minimal_atif()
        atif["steps"][0]["source"] = "policy-engine"
        atif["steps"][0]["message"] = [
            {"type": "text", "text": "known"},
            {"type": "audio", "source": {"path": "evidence.wav"}},
        ]
        canonical_doc, receipt = atif_to_canonical(atif)
        message = canonical_doc["events"][0]
        self.assertEqual(message["source_role"], "policy-engine")
        self.assertTrue(message["has_unknown_content_part"])
        self.assertEqual(message["content_parts"][1]["type"], "audio")
        unsupported_paths = {
            item["path"] for item in receipt["items"] if item["category"] == "unsupported"
        }
        self.assertIn("steps[0].message[1]", unsupported_paths)
        self.assertIn("steps[0].source", unsupported_paths)
        assert_no_silent_loss(receipt)

    def test_reward_in_extra_is_untrusted_evidence(self):
        atif = minimal_atif()
        atif["steps"][0]["metrics"] = {"extra": {"reward": 0.8}}
        canonical_doc, receipt = atif_to_canonical(atif)
        rewards = [
            item
            for item in canonical_doc["events"]
            if item["kind"] == "evaluation.recorded"
        ]
        self.assertEqual(rewards[0]["reward_total"], 0.8)
        self.assertEqual(rewards[0]["reward_trust"], "untrusted_atif_extra")
        self.assertTrue(
            any("atif.reward_in_extra" in item["reason"] for item in receipt["items"])
        )
        self.assertEqual(canonical_doc["outcome"]["source"], "missing")
        assert_no_silent_loss(receipt)

    def test_stable_atif_round_trip(self):
        original = minimal_atif()
        first, receipts = stable_round_trip(original)
        second, second_receipts = stable_round_trip(first)
        # Frankengate canonical IDs make the semantic event stream stable after
        # one canonicalization pass.
        first_canonical, _ = atif_to_canonical(first)
        second_canonical, _ = atif_to_canonical(second)
        self.assertEqual(first_canonical["events"], second_canonical["events"])
        for receipt in receipts + second_receipts:
            assert_no_silent_loss(receipt)

    def test_input_is_not_mutated(self):
        atif = minimal_atif()
        before = copy.deepcopy(atif)
        stable_round_trip(atif)
        self.assertEqual(atif, before)

    def test_invalid_step_order_and_call_reference_fail_closed(self):
        atif = minimal_atif()
        atif["steps"][0]["step_id"] = 2
        with self.assertRaisesRegex(ATIFValidationError, "sequential"):
            atif_to_canonical(atif)
        atif = minimal_atif()
        atif["steps"][0]["observation"]["results"][0]["source_call_id"] = "missing"
        with self.assertRaisesRegex(ATIFValidationError, "unknown tool_call_id"):
            atif_to_canonical(atif)

    def test_projection_receipt_schema_has_zero_silent_drop_contract(self):
        schema_path = ROOT / "schemas" / "atif-projection-loss-receipt.schema.json"
        schema = json.loads(schema_path.read_text())
        required = set(schema["required"])
        self.assertIn("silently_dropped_event_count", required)
        self.assertEqual(
            schema["properties"]["silently_dropped_event_count"]["const"], 0
        )
        self.assertIn("dropped", schema["properties"]["items"]["items"]["properties"]["category"]["enum"])


if __name__ == "__main__":
    unittest.main()
