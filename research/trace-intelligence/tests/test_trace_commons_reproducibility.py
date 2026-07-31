import copy
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from trace_commons_reproducibility import (  # noqa: E402
    METRIC_PATHS,
    compare,
)


def fixture(value=1):
    return {
        "S0_metadata": {
            "sessions": value,
            "valid_records": value,
            "malformed_records": 0,
        },
        "S1_deterministic_signals": {
            "candidate_sessions": value,
            "review_selected_sessions": value,
        },
        "S2_exact_structured_fts_ready": {"candidate_sessions": value},
        "S4_temporal_episode_candidates": {
            "candidate_episodes": value,
            "candidate_tiers": {"high": value, "medium": value, "low": value},
        },
        "S6_proposal_records": {
            "candidate_records": {
                "eval_review": value,
                "memory_review_motifs": value,
                "procedure_review_episodes": value,
                "skill_gap_recommendations": 0,
                "cross_user_collaboration_recommendations": 0,
                "automatic_memory_or_skill_writes": 0,
            }
        },
        "observed_failure_modes": {
            "outcome_labels_available": 0,
            "environment_state_snapshots_available": 0,
            "authorization_and_classification_labels_available": 0,
        },
    }


class TraceCommonsReproducibilityTests(unittest.TestCase):
    def test_matches_all_aggregate_paths_without_serializing_content(self):
        expected = fixture()
        actual = copy.deepcopy(expected)
        receipt = compare(
            actual=actual,
            expected=expected,
            expected_path=pathlib.Path("expected.json"),
            manifest_path=pathlib.Path("manifest.json"),
        )
        self.assertEqual(len(METRIC_PATHS), receipt["metrics_compared"])
        self.assertTrue(receipt["all_passed"])
        self.assertFalse(receipt["claim_boundary"]["causal_skill_benefit_confirmed"])
        self.assertFalse(receipt["raw_content_emitted"])

    def test_detects_one_aggregate_change(self):
        expected = fixture()
        actual = copy.deepcopy(expected)
        actual["S4_temporal_episode_candidates"]["candidate_tiers"]["high"] = 9
        receipt = compare(
            actual=actual,
            expected=expected,
            expected_path=pathlib.Path("expected.json"),
            manifest_path=pathlib.Path("manifest.json"),
        )
        self.assertFalse(receipt["all_passed"])
        self.assertFalse(
            next(
                row["matched"]
                for row in receipt["checks"]
                if row["metric"].endswith("candidate_tiers.high")
            )
        )


if __name__ == "__main__":
    unittest.main()
