import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from atif_capability_extension import (  # noqa: E402
    CapabilityExtensionError,
    PROFILE_URI,
    assert_capability_round_trip,
    atif_capability_to_canonical,
    canonical_to_atif_capability,
)


def event(event_id, sequence, kind, role, **fields):
    return {
        "event_id": event_id,
        "sequence": sequence,
        "kind": kind,
        "observation_status": "observed",
        "source_role": role,
        **fields,
    }


def canonical(events):
    return {
        "schema_version": "canonical-trajectory-v1",
        "trace_id": hashlib.sha256(b"capability-fixture").hexdigest(),
        "classification": "internal",
        "authorization_epoch": "epoch-7",
        "tenant_id": "tenant-a",
        "team_id": "team-a",
        "governance_scope": "chat",
        "environment_id": "alfworld",
        "environment_seed": 19,
        "environment_snapshot_ref": "sha256:reset",
        "memory_snapshot_before_ref": "sha256:mem-before",
        "memory_snapshot_after_ref": "sha256:mem-after",
        "memory_source_lineage_ref": "lineage:1",
        "memory_epoch": "mem-epoch-2",
        "source": {"dataset_id": "fixture"},
        "task": {"task_id": "task-1"},
        "events": events,
        "outcome": {"value": None, "source": "not_present"},
    }


class CapabilityExtensionTests(unittest.TestCase):
    def test_structural_facts_survive_and_payloads_do_not(self):
        source = canonical(
            [
                event(
                    "turn",
                    0,
                    "conversation.message",
                    "agent",
                    content="private prompt",
                ),
                event(
                    "reset",
                    1,
                    "environment.reset",
                    "environment",
                    parent_event_id="turn",
                    reset_id="reset-1",
                    state_before_ref="sha256:before",
                    state_after_ref="sha256:after",
                    termination_reason="reset",
                    state_delta={"private": "state"},
                ),
                event(
                    "reward",
                    2,
                    "evaluation.recorded",
                    "evaluator",
                    parent_event_id="turn",
                    reward_total=0.75,
                    reward_components={"correct": 1.0, "cost": -0.25},
                    authorization_epoch="epoch-7",
                    memory_snapshot_after={"private": "memory"},
                    token="must-not-leak",
                ),
            ]
        )
        before = copy.deepcopy(source)

        atif, export_receipt = canonical_to_atif_capability(source)
        extension = atif["extra"]["frankengate"]["capability_extension"]
        self.assertEqual(PROFILE_URI, extension["profile"])
        self.assertEqual("sha256", extension["contract"]["hash_algorithm"])
        self.assertIn("not-replayable", extension["contract"]["reference_policy"])
        self.assertEqual(3, extension["source_event_count"])
        # The generic ATIF envelope may still carry payloads; E0 redaction is
        # the separate policy boundary.  The capability profile itself must
        # never duplicate them.
        encoded = json.dumps(extension, sort_keys=True)
        self.assertNotIn("private prompt", encoded)
        self.assertNotIn("private", encoded)
        self.assertNotIn("must-not-leak", encoded)
        self.assertGreater(export_receipt["omitted_field_count"], 0)

        restored, import_receipt = atif_capability_to_canonical(atif)
        self.assertEqual("epoch-7", restored["authorization_epoch"])
        self.assertEqual("sha256:reset", restored["environment_snapshot_ref"])
        self.assertEqual("sha256:mem-after", restored["memory_snapshot_after_ref"])
        reward = next(item for item in restored["events"] if item["event_id"] == "reward")
        self.assertEqual(0.75, reward["reward_total"])
        self.assertNotIn("token", reward)
        self.assertEqual(0, import_receipt["silently_dropped_event_count"])
        self.assertEqual(before, source)

    def test_missing_unprojected_event_is_restored_from_extension(self):
        source = canonical(
            [
                event(
                    "unknown",
                    0,
                    "provider.future.event",
                    "provider",
                    authorization_epoch="epoch-7",
                    memory_candidate_id="candidate-1",
                )
            ]
        )
        atif, _ = canonical_to_atif_capability(source)
        restored, _ = atif_capability_to_canonical(atif)
        self.assertEqual(
            {item["event_id"] for item in restored["events"]}, {"unknown"}
        )
        restored_event = restored["events"][0]
        self.assertEqual("provider.future.event", restored_event["kind"])
        self.assertEqual("candidate-1", restored_event["memory_candidate_id"])

    def test_round_trip_helper_and_conflict_detection(self):
        source = canonical(
            [
                event(
                    "turn",
                    0,
                    "conversation.message",
                    "agent",
                    authorization_epoch="epoch-7",
                )
            ]
        )
        summary = assert_capability_round_trip(source)
        self.assertGreater(summary["retained_event_field_count"], 0)

        atif, _ = canonical_to_atif_capability(source)
        atif["steps"][0]["extra"]["frankengate"]["canonical_metadata"][
            "authorization_epoch"
        ] = "epoch-conflict"
        with self.assertRaises(CapabilityExtensionError):
            atif_capability_to_canonical(atif)


if __name__ == "__main__":
    unittest.main()
