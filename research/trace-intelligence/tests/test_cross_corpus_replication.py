import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "cross_corpus_replication.py"
)
SPEC = importlib.util.spec_from_file_location(
    "cross_corpus_replication", MODULE_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def fixture_aggregates():
    wisp = {
        "schema_version": "content-minimized-real-user-arms-v1",
        "source": {"dataset": "wisp", "revision": "wisp-revision"},
        "privacy_contract": {
            "content_fields_read_for_analysis": False,
            "raw_data_committed": False,
        },
        "S0_metadata": {
            "sessions": 10,
            "tool_calls": 102,
            "tool_results": 100,
            "unlinked_tool_results": 1,
        },
        "S1_deterministic_signals": {
            "signal_events": {"explicit_tool_errors": 20}
        },
        "S2_exact_structured_fts_ready": {
            "query_candidate_counts": {"explicit_error": 4}
        },
        "S4_temporal_episode_candidates": {
            "candidate_episodes": 12,
            "candidate_sessions": 3,
            "candidate_tiers": {"high": 4, "medium": 4, "low": 4},
        },
    }
    share = {
        "schema_version": "share-codex-sparse-pilot-v1",
        "source": {
            "dataset_id": "share",
            "dataset_revision": "share-revision",
        },
        "privacy": {
            "raw_data_committed": False,
            "content_emitted": False,
        },
        "coverage": {"sessions": 20},
        "lifecycle": {
            "tool_proposals": 202,
            "tool_results": 200,
            "matched_tool_results": 199,
            "explicit_error_results": 10,
            "sessions_with_explicit_error": 5,
            "error_results_with_later_success": 6,
            "sessions_with_error_then_later_success": 4,
            "error_results_with_later_same_tool_success": 3,
        },
    }
    return wisp, share


class CrossCorpusReplicationTest(unittest.TestCase):
    def test_wilson_interval_known_boundaries(self):
        lower, upper = MODULE.wilson_interval(0, 10)
        self.assertEqual(0.0, lower)
        self.assertAlmostEqual(0.277533, upper, places=6)
        lower, upper = MODULE.wilson_interval(10, 10)
        self.assertAlmostEqual(0.722467, lower, places=6)
        self.assertEqual(1.0, upper)

    def test_aligned_and_non_aligned_metrics_are_distinct(self):
        wisp, share = fixture_aggregates()
        result = MODULE.compare_aggregates(wisp, share)
        linked = result["metrics"]["matched_tool_result_share"]
        recovery = result["metrics"][
            "error_to_later_success_candidate_share"
        ]

        self.assertEqual("aligned", linked["comparability"])
        self.assertIn(
            "observed_difference_share_codex_minus_wisp", linked
        )
        self.assertEqual("not_aligned", recovery["comparability"])
        self.assertNotIn(
            "observed_difference_share_codex_minus_wisp", recovery
        )

    def test_denominators_are_explicit_and_concentration_is_descriptive(self):
        wisp, share = fixture_aggregates()
        result = MODULE.compare_aggregates(wisp, share)
        errors = result["metrics"]["explicit_error_result_share"]

        self.assertEqual("tool results", errors["wisp"]["denominator_unit"])
        self.assertEqual(20, errors["wisp"]["successes"])
        self.assertEqual(100, errors["wisp"]["total"])
        self.assertEqual(
            "descriptive_only",
            result["session_concentration"]["comparability"],
        )

    def test_raw_or_content_bearing_input_fails_closed(self):
        wisp, share = fixture_aggregates()
        share["privacy"]["raw_data_committed"] = True
        with self.assertRaisesRegex(ValueError, "committed raw data"):
            MODULE.compare_aggregates(wisp, share)

    def test_result_copies_no_transcript_content(self):
        wisp, share = fixture_aggregates()
        wisp["SECRET_PROMPT"] = "DO NOT COPY"
        share["SECRET_TOOL_OUTPUT"] = "DO NOT COPY"
        result = MODULE.compare_aggregates(wisp, share)
        self.assertNotIn("DO NOT COPY", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
