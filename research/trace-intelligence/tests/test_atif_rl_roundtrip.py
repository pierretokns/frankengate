import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from atif_rl_roundtrip import (  # noqa: E402
    CAPABILITIES,
    aggregate_comparisons,
    capability_facts,
    compare_trajectory,
)


def canonical(events, **fields):
    return {
        "schema_version": "canonical-trajectory-v1",
        "trace_id": "a" * 64,
        "source": {
            "dataset_id": "fixture/source",
            "dataset_revision": "fixture-revision",
            "adapter": "fixture-adapter",
            "source_file_sha256": "b" * 64,
        },
        "task": {"task_id": "fixture-task"},
        "events": events,
        "outcome": {"value": None, "source": "not_present"},
        "loss_receipt": {
            "source_event_count": len(events),
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
        },
        **fields,
    }


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


class CapabilityFactTest(unittest.TestCase):
    def test_extracts_only_observed_capability_facts(self):
        source = canonical(
            [
                event("turn", 0, "conversation.message", "agent", "work"),
                event(
                    "call",
                    1,
                    "tool.proposed",
                    "agent",
                    parent_event_id="turn",
                    tool_call_id="c1",
                    function_name="shell",
                    arguments={"command": "pwd"},
                    attempt=2,
                    timestamp="2026-07-30T12:00:00Z",
                ),
                event(
                    "result",
                    2,
                    "tool.completed",
                    "tool",
                    "ok",
                    parent_event_id="call",
                    tool_call_id="c1",
                ),
            ]
        )

        facts = capability_facts(source)

        self.assertEqual(set(CAPABILITIES), set(facts))
        self.assertGreater(len(facts["tool_calls"]), 0)
        self.assertGreater(len(facts["tool_results"]), 0)
        self.assertGreater(len(facts["retries"]), 0)
        self.assertGreater(len(facts["observations"]), 0)
        self.assertGreater(len(facts["time"]), 0)
        self.assertGreater(len(facts["provenance"]), 0)
        self.assertGreater(len(facts["replay_identity"]), 0)
        self.assertEqual(set(), facts["authorization"])
        self.assertEqual(set(), facts["rewards"])
        self.assertEqual(set(), facts["environment_reset_state"])

    def test_negative_branch_flags_and_payload_key_collisions_are_not_facts(self):
        source = canonical(
            [
                event(
                    "turn",
                    0,
                    "conversation.message",
                    "agent",
                    "work",
                    path_context={
                        "is_subagent_workflow": False,
                        "workflow_id": None,
                    },
                    arguments={
                        "branch_id": "tool-payload-not-trace-topology",
                        "success": True,
                    },
                )
            ]
        )

        facts = capability_facts(source)

        self.assertEqual(set(), facts["branches"])
        self.assertEqual(set(), facts["termination"])

    def test_profiled_roundtrips_report_fact_retention_without_mutation(self):
        source = canonical(
            [
                event("turn", 0, "conversation.message", "agent", "work"),
                event(
                    "call",
                    1,
                    "tool.proposed",
                    "agent",
                    parent_event_id="turn",
                    tool_call_id="c1",
                    function_name="shell",
                    arguments={"command": "pwd"},
                    timestamp="2026-07-30T12:00:00Z",
                ),
                event(
                    "result",
                    2,
                    "tool.completed",
                    "tool",
                    "ok",
                    parent_event_id="call",
                    tool_call_id="c1",
                ),
            ]
        )
        before = copy.deepcopy(source)

        comparison = compare_trajectory(source)

        self.assertEqual(before, source)
        self.assertEqual(1.0, comparison["canonical"]["overall_retention"])
        self.assertEqual(
            1.0,
            comparison["ATIF_v1_7_profiled"]["capabilities"]["tool_calls"][
                "retention"
            ],
        )
        self.assertLess(
            comparison["OpenInference_OTel_profiled"]["capabilities"][
                "tool_results"
            ]["retention"],
            1.0,
        )
        self.assertEqual(
            0,
            comparison["ATIF_v1_7_profiled"]["silent_drop_count"],
        )
        self.assertEqual(
            0,
            comparison["OpenInference_OTel_profiled"]["silent_drop_count"],
        )
        self.assertEqual(
            1.0,
            comparison["OpenInference_OTel_profiled"]["capabilities"]["time"][
                "retention"
            ],
        )
        self.assertNotIn("ok", json.dumps(comparison))

    def test_family_aggregation_distinguishes_absence_from_loss(self):
        source = canonical(
            [
                event("turn", 0, "conversation.message", "agent", "private"),
                event(
                    "call",
                    1,
                    "tool.proposed",
                    "agent",
                    parent_event_id="turn",
                    tool_call_id="c1",
                    function_name="shell",
                    arguments={"command": "private-command"},
                ),
                event(
                    "result",
                    2,
                    "tool.completed",
                    "tool",
                    "private-result",
                    parent_event_id="call",
                    tool_call_id="c1",
                ),
            ]
        )

        aggregate = aggregate_comparisons([compare_trajectory(source)])

        self.assertEqual(1, aggregate["trajectory_count"])
        self.assertEqual(
            "not_observed",
            aggregate["source_capabilities"]["authorization"]["source_status"],
        )
        self.assertIsNone(
            aggregate["formats"]["canonical"]["capabilities"]["authorization"][
                "retention"
            ]
        )
        self.assertEqual(
            1.0,
            aggregate["formats"]["canonical"]["capabilities"]["tool_calls"][
                "retention"
            ],
        )
        encoded = json.dumps(aggregate)
        self.assertNotIn("private-command", encoded)
        self.assertNotIn("private-result", encoded)


if __name__ == "__main__":
    unittest.main()
