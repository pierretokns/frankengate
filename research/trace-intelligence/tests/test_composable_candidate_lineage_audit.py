from __future__ import annotations

import unittest
from pathlib import Path

from composable_candidate_lineage_audit import build_audit, digest, load


ROOT = Path(__file__).resolve().parents[1]


class ComposableCandidateLineageAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.aggregate = load(ROOT / "experiments/results/composable-artifact-frontier-replay-2026-08-04-aggregate-rerun.json")
        self.seed_a = load(ROOT / "experiments/results/composable-artifact-frontier-replay-2026-08-04-seed840000-rerun.json")
        self.seed_b = load(ROOT / "experiments/results/composable-artifact-frontier-replay-2026-08-04-seed850000.json")
        self.verify_a = load(ROOT / "experiments/results/composable-artifact-frontier-replay-2026-08-04-seed840000-rerun-verification.json")
        self.verify_b = load(ROOT / "experiments/results/composable-artifact-frontier-replay-2026-08-04-seed850000-verification.json")

    def build(self) -> dict:
        return build_audit(
            aggregate=self.aggregate,
            seed_a=self.seed_a,
            seed_b=self.seed_b,
            verify_a=self.verify_a,
            verify_b=self.verify_b,
        )

    def test_same_candidate_identity_and_replay_are_verified(self) -> None:
        result = self.build()
        self.assertTrue(result["checks"]["candidate_identity_stable"])
        self.assertTrue(result["checks"]["candidate_stable_semantic_success"])
        self.assertTrue(result["checks"]["independent_semantic_verifiers_passed"])
        self.assertEqual(result["replay"]["candidate_semantic_correct"], [5, 5])
        self.assertEqual(result["replay"]["no_skill_semantic_correct"], [3, 2])

    def test_claim_boundary_reconciliation_gap_is_not_hidden(self) -> None:
        result = self.build()
        self.assertTrue(result["checks"]["aggregate_source_target_split_declared"])
        self.assertFalse(result["checks"]["seed_source_target_split_boundaries_reconciled"])
        self.assertFalse(result["gates_closed"]["source_target_disjointness"])
        self.assertTrue(result["gates_open"]["aggregate_vs_seed_claim_boundary_reconciliation"])
        self.assertFalse(result["claim_boundary"]["production_promotion_established"])

    def test_receipt_hash_is_stable(self) -> None:
        result = self.build()
        unsigned = dict(result)
        unsigned.pop("result_sha256")
        self.assertEqual(result["result_sha256"], digest(unsigned))


if __name__ == "__main__":
    unittest.main()
