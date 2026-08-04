import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from canonical_recovery_episodes import (  # noqa: E402
    EVENT_ERROR,
    EVENT_PROPOSED,
    EVENT_SUCCESS,
    EpisodeConstructionError,
    LifecycleEvent,
    aggregate_share_codex,
    construct_recovery_episodes,
    lifecycle_from_share_codex_row,
    lifecycle_from_wisp_records,
    run_comparison,
    tool_family,
)


def proposed(order, key, family="shell"):
    return LifecycleEvent(order, EVENT_PROPOSED, key, family)


def error(order, key):
    return LifecycleEvent(order, EVENT_ERROR, key, None)


def success(order, key):
    return LifecycleEvent(order, EVENT_SUCCESS, key, None)


class CanonicalRecoveryEpisodeTests(unittest.TestCase):
    def test_new_same_family_call_after_error_forms_episode(self):
        result = construct_recovery_episodes(
            [
                proposed(0, "failed"),
                error(1, "failed"),
                proposed(2, "retry"),
                success(3, "retry"),
            ]
        )
        self.assertEqual(1, len(result.matched_episodes))
        episode = result.matched_episodes[0]
        self.assertEqual("shell", episode.tool_family)
        self.assertEqual(2, episode.lifecycle_distance)

    def test_in_flight_parallel_call_is_not_a_recovery(self):
        result = construct_recovery_episodes(
            [
                proposed(0, "failed"),
                proposed(1, "parallel"),
                error(2, "failed"),
                success(3, "parallel"),
            ]
        )
        self.assertEqual(0, len(result.matched_episodes))
        self.assertEqual(1, result.excluded_in_flight_candidate_pairs)

    def test_greedy_matching_is_one_to_one(self):
        result = construct_recovery_episodes(
            [
                proposed(0, "failed-1"),
                error(1, "failed-1"),
                proposed(2, "failed-2"),
                error(3, "failed-2"),
                proposed(4, "only-success"),
                success(5, "only-success"),
            ]
        )
        self.assertEqual(1, len(result.matched_episodes))
        self.assertEqual(1, result.unmatched_eligible_error_results)
        self.assertEqual(1, result.matched_episodes[0].error_order)

    def test_earliest_success_is_chosen_deterministically(self):
        result = construct_recovery_episodes(
            [
                proposed(0, "failed"),
                error(1, "failed"),
                proposed(2, "later"),
                proposed(3, "earlier"),
                success(4, "earlier"),
                success(5, "later"),
            ]
        )
        self.assertEqual(4, result.matched_episodes[0].recovery_result_order)

    def test_window_is_inclusive_and_bounded_on_success_result(self):
        at_boundary = construct_recovery_episodes(
            [
                proposed(0, "failed"),
                error(1, "failed"),
                proposed(2, "retry"),
                success(3, "retry"),
            ],
            max_lifecycle_distance=2,
        )
        self.assertEqual(1, len(at_boundary.matched_episodes))

        outside = construct_recovery_episodes(
            [
                proposed(0, "failed"),
                error(1, "failed"),
                proposed(2, "retry"),
                proposed(3, "filler", "file_read"),
                success(4, "retry"),
            ],
            max_lifecycle_distance=2,
        )
        self.assertEqual(0, len(outside.matched_episodes))
        self.assertEqual(1, outside.excluded_out_of_window_candidate_pairs)

    def test_different_family_is_not_a_recovery(self):
        result = construct_recovery_episodes(
            [
                proposed(0, "failed", "shell"),
                error(1, "failed"),
                proposed(2, "success", "file_read"),
                success(3, "success"),
            ]
        )
        self.assertEqual(0, len(result.matched_episodes))

    def test_unlinked_and_unmapped_errors_are_explicitly_excluded(self):
        result = construct_recovery_episodes(
            [
                error(0, "missing"),
                proposed(1, "custom", None),
                error(2, "custom"),
            ]
        )
        self.assertEqual(1, result.excluded_unlinked_error_results)
        self.assertEqual(1, result.excluded_unmapped_error_results)
        self.assertEqual(0, result.eligible_error_results)

    def test_duplicate_call_keys_are_not_treated_as_unique_linkage(self):
        result = construct_recovery_episodes(
            [
                proposed(0, "duplicate"),
                proposed(1, "duplicate"),
                error(2, "duplicate"),
            ]
        )
        self.assertEqual(0, result.linked_error_results)
        self.assertEqual(1, result.excluded_unlinked_error_results)

    def test_multiple_results_for_one_call_are_not_unique_linkage(self):
        result = construct_recovery_episodes(
            [
                proposed(0, "duplicate-result"),
                error(1, "duplicate-result"),
                success(2, "duplicate-result"),
            ]
        )
        self.assertEqual(0, result.linked_error_results)
        self.assertEqual(0, result.linked_success_results)

    def test_non_dense_or_invalid_lifecycle_is_rejected(self):
        with self.assertRaises(EpisodeConstructionError):
            construct_recovery_episodes([proposed(1, "x")])
        with self.assertRaises(EpisodeConstructionError):
            construct_recovery_episodes(
                [LifecycleEvent(0, "conversation.text", None, None)]
            )
        with self.assertRaises(EpisodeConstructionError):
            construct_recovery_episodes([], max_lifecycle_distance=0)

    def test_wisp_and_share_codex_isomorphic_input_matches(self):
        wisp = [
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "w-error",
                            "name": "Bash",
                        }
                    ]
                }
            },
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "w-error",
                            "is_error": True,
                        }
                    ]
                }
            },
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "w-retry",
                            "name": "Bash",
                        }
                    ]
                }
            },
            {
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "w-retry",
                            "is_error": False,
                        }
                    ]
                }
            },
        ]
        share = {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "s-error",
                            "function": {"name": "exec_command"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "s-error",
                    "metadata": {"is_error": True},
                },
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "s-retry",
                            "function": {"name": "exec_command"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "s-retry",
                    "metadata": {"is_error": False},
                },
            ]
        }
        wisp_result = construct_recovery_episodes(
            lifecycle_from_wisp_records(wisp)
        )
        share_result = construct_recovery_episodes(
            lifecycle_from_share_codex_row(share)
        )
        self.assertEqual(1, len(wisp_result.matched_episodes))
        self.assertEqual(1, len(share_result.matched_episodes))
        self.assertEqual(
            wisp_result.matched_episodes[0].tool_family,
            share_result.matched_episodes[0].tool_family,
        )
        self.assertEqual(
            wisp_result.matched_episodes[0].lifecycle_distance,
            share_result.matched_episodes[0].lifecycle_distance,
        )

    def test_known_names_map_to_shared_families_and_custom_does_not(self):
        self.assertEqual("shell", tool_family("Bash"))
        self.assertEqual("shell", tool_family("exec_command"))
        self.assertEqual("file_change", tool_family("Edit"))
        self.assertEqual("file_change", tool_family("apply_patch"))
        self.assertIsNone(tool_family("CompanySpecificTool"))

    def test_share_codex_revision_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory)
            (sample / "share-codex.rows-0.json").write_text(
                json.dumps({"partial": False, "rows": []}),
                encoding="utf-8",
            )
            (sample / "share-codex.rows-0.headers").write_text(
                "x-revision: wrong\n",
                encoding="utf-8",
            )
            with self.assertRaises(EpisodeConstructionError):
                aggregate_share_codex(
                    sample,
                    expected_revision="expected",
                    max_lifecycle_distance=12,
                )

    def test_empty_corpora_and_incomplete_pinned_sample_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory)
            with self.assertRaises(EpisodeConstructionError):
                aggregate_share_codex(
                    empty,
                    expected_revision="revision",
                    max_lifecycle_distance=12,
                )

            (empty / "share-codex.rows-0.json").write_text(
                json.dumps(
                    {
                        "partial": False,
                        "num_rows_total": 10,
                        "rows": [],
                    }
                ),
                encoding="utf-8",
            )
            (empty / "share-codex.rows-0.headers").write_text(
                "x-revision: revision\n",
                encoding="utf-8",
            )
            with self.assertRaises(EpisodeConstructionError):
                aggregate_share_codex(
                    empty,
                    expected_revision="revision",
                    max_lifecycle_distance=12,
                    expected_requests=[
                        {"offset": 0, "length": 0},
                        {"offset": 5, "length": 0},
                    ],
                    expected_population_rows=10,
                )

    def test_error_like_text_is_not_an_explicit_typed_error(self):
        row = {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call",
                            "function": {"name": "exec_command"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call",
                    "content": "ERROR: this text must not be classified",
                    "metadata": {},
                },
            ]
        }
        events = lifecycle_from_share_codex_row(row)
        self.assertEqual(EVENT_SUCCESS, events[-1].kind)
        result = construct_recovery_episodes(events)
        self.assertEqual(0, result.error_results)

    def test_comparison_output_is_aggregate_only(self):
        canary_content = "DO_NOT_EMIT_TRANSCRIPT_CONTENT"
        canary_call_id = "DO_NOT_EMIT_CALL_ID"
        canary_session_id = "DO_NOT_EMIT_SESSION_ID"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wisp_root = root / "wisp"
            share_root = root / "share"
            wisp_root.mkdir()
            share_root.mkdir()
            records = [
                {
                    "sessionId": canary_session_id,
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": canary_call_id,
                                "name": "Bash",
                                "input": {"secret": canary_content},
                            }
                        ]
                    },
                },
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": canary_call_id,
                                "is_error": True,
                                "content": canary_content,
                            }
                        ]
                    }
                },
            ]
            (wisp_root / "private-path.jsonl").write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )
            row = {
                "id": canary_session_id,
                "messages": [
                    {
                        "role": "user",
                        "content": canary_content,
                    }
                ],
            }
            (share_root / "share-codex.rows-0.json").write_text(
                json.dumps(
                    {
                        "partial": False,
                        "num_rows_total": 1,
                        "rows": [{"row_idx": 0, "row": row}],
                    }
                ),
                encoding="utf-8",
            )
            (share_root / "share-codex.rows-0.headers").write_text(
                "x-revision: revision\n",
                encoding="utf-8",
            )
            manifest_base = {
                "dataset_revision": "revision",
                "sample_design": {"name": "fixture"},
            }
            output = run_comparison(
                wisp_root=wisp_root,
                share_codex_sample_dir=share_root,
                wisp_manifest={
                    **manifest_base,
                    "dataset_id": "wisp-fixture",
                },
                share_codex_manifest={
                    **manifest_base,
                    "dataset_id": "share-fixture",
                    "population_rows": 1,
                    "sample_design": {
                        "name": "fixture",
                        "requests": [{"offset": 0, "length": 1}],
                    },
                },
            )
            serialized = json.dumps(output, sort_keys=True)
            for forbidden in (
                canary_content,
                canary_call_id,
                canary_session_id,
                "private-path",
                "row_idx",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_constructor_is_deterministic(self):
        events = [
            proposed(0, "failed"),
            error(1, "failed"),
            proposed(2, "retry"),
            success(3, "retry"),
        ]
        self.assertEqual(
            construct_recovery_episodes(events),
            construct_recovery_episodes(events),
        )


if __name__ == "__main__":
    unittest.main()
