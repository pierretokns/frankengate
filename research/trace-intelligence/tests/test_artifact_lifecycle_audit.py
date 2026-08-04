from __future__ import annotations

import json
import unittest
from pathlib import Path

from artifact_lifecycle_audit import build_audit, digest, load


ROOT = Path(__file__).resolve().parents[1]


class ArtifactLifecycleAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frontier = load(ROOT / "experiments/results/dataclaw-artifact-frontier-screen-2026-08-05.json")
        self.replay = load(ROOT / "experiments/results/artifact-changed-system-replay-2026-08-03.json")
        self.stress = load(ROOT / "experiments/results/artifact-subplan-changed-system-stress-2026-08-05.json")
        self.promotion = load(ROOT / "experiments/results/artifact-promotion-audit-2026-08-02.json")
        self.drift = load(ROOT / "experiments/results/claude-history-tool-artifact-drift-2026-08-09.json")
        self.memory = load(ROOT / "experiments/results/bitemporal-memory-conformance-2026-07-30.json")

    def test_lifecycle_states_and_boundaries(self) -> None:
        result = build_audit(
            frontier=self.frontier,
            replay=self.replay,
            stress=self.stress,
            promotion=self.promotion,
            drift=self.drift,
            memory=self.memory,
        )
        self.assertEqual(result["frontier_lifecycle"]["candidate_count"], 8)
        self.assertEqual(
            result["frontier_lifecycle"]["states"],
            {
                "replay_pending": 2,
                "blocked_safety": 1,
                "blocked_evidence": 1,
                "blocked_disagreement": 2,
                "scope_bound": 2,
            },
        )
        self.assertEqual(result["frontier_lifecycle"]["promotion_ready_count"], 0)
        self.assertFalse(result["claim_boundary"]["replay_receipts_share_candidate_ids_with_frontier"])
        self.assertFalse(result["claim_boundary"]["skill_or_artifact_user_benefit_established"])

    def test_replay_safety_invariants(self) -> None:
        result = build_audit(
            frontier=self.frontier,
            replay=self.replay,
            stress=self.stress,
            promotion=self.promotion,
            drift=self.drift,
            memory=self.memory,
        )
        invariants = result["invariants"]
        self.assertTrue(invariants["name_only_false_accepts_observed"])
        self.assertTrue(invariants["semantic_false_accepts_absent"])
        self.assertTrue(invariants["stress_name_only_unsafe_accepts_observed"])
        self.assertTrue(invariants["stress_semantic_unsafe_accepts_observed"])

    def test_receipt_hash_is_stable(self) -> None:
        result = build_audit(
            frontier=self.frontier,
            replay=self.replay,
            stress=self.stress,
            promotion=self.promotion,
            drift=self.drift,
            memory=self.memory,
        )
        unsigned = dict(result)
        unsigned.pop("result_sha256")
        self.assertEqual(result["result_sha256"], digest(unsigned))


if __name__ == "__main__":
    unittest.main()
