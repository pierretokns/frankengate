import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1] / "bitemporal_memory_conformance.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bitemporal_memory_conformance", MODULE_PATH
)
memory = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = memory
SPEC.loader.exec_module(memory)


def private_envelope(**kwargs):
    values = {
        "tenant_id": "tenant-a",
        "owner_subject_id": "alice",
        "audience": "private",
        "team_id": None,
        "classification": 1,
        "purposes": ("support", "debug"),
        "authorization_epoch": 3,
        "policy_revision": "policy-v1",
    }
    values.update(kwargs)
    return memory.Envelope(**values)


class BitemporalMemoryConformanceTest(unittest.TestCase):
    def test_scope_intersection_is_fail_closed(self):
        left = private_envelope(classification=2)
        right = private_envelope(
            classification=4, purposes=("support", "audit")
        )
        result = memory.intersect_envelopes((left, right))
        self.assertEqual(4, result.classification)
        self.assertEqual(("support",), result.purposes)
        with self.assertRaises(memory.ConformanceError):
            memory.intersect_envelopes(
                (left, private_envelope(purposes=("audit",)))
            )
        with self.assertRaises(memory.ConformanceError):
            memory.intersect_envelopes(
                (left, private_envelope(tenant_id="tenant-b"))
            )

    def test_valid_and_system_time_preserve_correction_history(self):
        ledger = memory.MemoryLedger()
        envelope = private_envelope()
        authority = memory.QueryAuthority(
            tenant_id="tenant-a",
            subject_id="alice",
            teams=(),
            classification_ceiling=2,
            purpose="support",
            authorization_epoch=3,
        )
        old = memory.Evidence(
            "old",
            "endpoint",
            (("environment", "prod"),),
            "v1",
            memory.instant("2026-01-01T00:00:00Z"),
            memory.instant("2026-01-02T00:00:00Z"),
            envelope,
        )
        new = memory.Evidence(
            "new",
            "endpoint",
            (("environment", "prod"),),
            "v2",
            memory.instant("2026-06-01T00:00:00Z"),
            memory.instant("2026-07-01T00:00:00Z"),
            envelope,
        )
        ledger.add_evidence(old)
        ledger.add_evidence(new)
        old_candidate = ledger.propose(
            fact_key="endpoint",
            context={"environment": "prod"},
            value="v1",
            valid_from=old.valid_from,
            evidence_ids=("old",),
        )
        ledger.review(old_candidate.candidate_id)
        release_one = ledger.promote(
            old_candidate.candidate_id,
            dream_job_status="completed",
            created_at=memory.instant("2026-02-01T00:00:00Z"),
        )
        new_candidate = ledger.propose(
            fact_key="endpoint",
            context={"environment": "prod"},
            value="v2",
            valid_from=new.valid_from,
            evidence_ids=("new",),
            parent_candidate_ids=(old_candidate.candidate_id,),
        )
        ledger.review(new_candidate.candidate_id)
        ledger.promote(
            new_candidate.candidate_id,
            dream_job_status="completed",
            created_at=memory.instant("2026-08-01T00:00:00Z"),
        )
        self.assertIsNone(release_one.entries[0].valid_to)

        before_system = ledger.query(
            fact_key="endpoint",
            context={"environment": "prod"},
            valid_at=memory.instant("2026-07-01T00:00:00Z"),
            system_at=memory.instant("2026-03-01T00:00:00Z"),
            authority=authority,
        )
        after_system_old_valid = ledger.query(
            fact_key="endpoint",
            context={"environment": "prod"},
            valid_at=memory.instant("2026-05-01T00:00:00Z"),
            system_at=memory.instant("2026-09-01T00:00:00Z"),
            authority=authority,
        )
        after_system_new_valid = ledger.query(
            fact_key="endpoint",
            context={"environment": "prod"},
            valid_at=memory.instant("2026-07-01T00:00:00Z"),
            system_at=memory.instant("2026-09-01T00:00:00Z"),
            authority=authority,
        )
        self.assertEqual(["v1"], [item.value for item in before_system])
        self.assertEqual(["v1"], [item.value for item in after_system_old_valid])
        self.assertEqual(["v2"], [item.value for item in after_system_new_valid])

    def test_failed_job_cannot_promote(self):
        ledger = memory.MemoryLedger()
        evidence = memory.Evidence(
            "e",
            "fact",
            (),
            "value",
            memory.instant("2026-01-01T00:00:00Z"),
            memory.instant("2026-01-02T00:00:00Z"),
            private_envelope(),
        )
        ledger.add_evidence(evidence)
        candidate = ledger.propose(
            fact_key="fact",
            context={},
            value="value",
            valid_from=evidence.valid_from,
            evidence_ids=("e",),
        )
        ledger.review(candidate.candidate_id)
        with self.assertRaises(memory.ConformanceError):
            ledger.promote(
                candidate.candidate_id,
                dream_job_status="failed",
                created_at=memory.instant("2026-02-01T00:00:00Z"),
            )

    def test_contextual_difference_does_not_create_contradiction(self):
        result = memory.run_conformance()
        self.assertIn(
            "different_context_not_invalidated", result["assertions"]["names"]
        )
        self.assertEqual(
            result["assertions"]["total"], result["assertions"]["passed"]
        )

    def test_deletion_closure_and_influence_gate_are_exercised(self):
        result = memory.run_conformance()
        aggregate = result["ledger_aggregate"]
        self.assertGreaterEqual(aggregate["invalidated_releases"], 1)
        self.assertEqual(1, aggregate["invalidated_exports"])
        self.assertIn(
            "influenced_trace_not_independent_validation",
            result["assertions"]["names"],
        )

    def test_run_is_deterministic_and_claim_limited(self):
        first = memory.run_conformance()
        second = memory.run_conformance()
        self.assertEqual(first, second)
        self.assertFalse(first["study_scope"]["database_or_rls_executed"])
        self.assertFalse(first["study_scope"]["model_extractor_executed"])
        self.assertIn(
            "memory benefit on held-out tasks or natural enterprise traces",
            first["not_proven"],
        )


if __name__ == "__main__":
    unittest.main()
