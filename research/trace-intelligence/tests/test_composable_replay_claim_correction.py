from __future__ import annotations

import unittest
from pathlib import Path

from composable_replay_claim_correction import build_correction, digest, load


ROOT = Path(__file__).resolve().parents[1]


class ComposableReplayClaimCorrectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.aggregate = load(ROOT / "experiments/results/composable-artifact-frontier-replay-2026-08-04-aggregate-rerun.json")
        self.seed_a = load(ROOT / "experiments/results/composable-artifact-frontier-replay-2026-08-04-seed840000-rerun.json")
        self.seed_b = load(ROOT / "experiments/results/composable-artifact-frontier-replay-2026-08-04-seed850000.json")
        self.candidate = load(ROOT / "experiments/results/composable-artifact-candidate-2026-08-04.json")
        self.manifest = load(ROOT / "experiments/manifests/defog-sql-eval-enterprise-96-2026-07-30.json")

    def build(self) -> dict:
        return build_correction(
            aggregate=self.aggregate,
            seed_a=self.seed_a,
            seed_b=self.seed_b,
            candidate=self.candidate,
            cohort_manifest=self.manifest,
        )

    def test_manifest_backed_correction(self) -> None:
        result = self.build()
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["reconstructed_cohort"]["source_manifest_rows"], 19)
        self.assertEqual(result["reconstructed_cohort"]["candidate_artifacts"], 18)
        self.assertEqual(result["reconstructed_cohort"]["target_manifest_rows"], 5)
        self.assertEqual(result["reconstructed_cohort"]["source_target_hash_overlap"], 0)
        self.assertFalse(result["corrected_claim_boundary"]["changed_system_replay_verified"])
        self.assertFalse(result["corrected_claim_boundary"]["promotion_authorized"])

    def test_hash_is_stable(self) -> None:
        result = self.build()
        unsigned = dict(result)
        unsigned.pop("result_sha256")
        self.assertEqual(result["result_sha256"], digest(unsigned))


if __name__ == "__main__":
    unittest.main()
