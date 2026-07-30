import copy
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from cmu_agent_trajectories import (  # noqa: E402
    CMUAdapterError,
    analyze_rows,
    canonicalize_cmu,
    deterministic_attempt_features,
    repeated_pass_group_key,
)


def source_row(*, source_id="row-1", pass_number=1, reward=0.0, error=True):
    result = (
        '{"status":"error","error":"synthetic failure"}'
        if error
        else '{"status":"ok","value":"synthetic success"}'
    )
    return {
        "id": source_id,
        "benchmark": "terminalbench",
        "domain": "fixture-domain",
        "task_id": "fixture-task",
        "source_model": "fixture-model",
        "pass": pass_number,
        "messages": [
            {"role": "system", "content": "synthetic system"},
            {"role": "user", "content": "synthetic task"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call-{pass_number}",
                        "type": "function",
                        "function": {
                            "name": "fixture_tool",
                            "arguments": '{"fixture":true}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": f"call-{pass_number}",
                "content": result,
            },
            {"role": "assistant", "content": "synthetic terminal answer"},
        ],
        "num_turns": 5,
        "reward": reward,
        "eval_details": {"fixture": True},
        "trace_meta": {"fixture": True},
        "cleaning_info": None,
        "num_passes_available": 4,
        "has_all_4_passes": True,
    }


class CMUAdapterTests(unittest.TestCase):
    def test_preserves_every_message_and_observed_tool_lifecycle(self):
        canonical = canonicalize_cmu(source_row())
        self.assertEqual("canonical-trajectory-v1", canonical["schema_version"])
        self.assertEqual(
            "cx-cmu/agent_trajectories",
            canonical["source"]["dataset_id"],
        )
        receipt = canonical["loss_receipt"]
        self.assertEqual(5, receipt["source_event_count"])
        self.assertEqual(5, receipt["source_messages_preserved"])
        self.assertEqual(1, receipt["source_tool_calls_observed"])
        self.assertEqual(1, receipt["source_tool_results_observed"])
        self.assertEqual(0, receipt["silently_dropped_event_count"])
        self.assertEqual([], receipt["reconstructed_fields"])

        proposals = [
            event
            for event in canonical["events"]
            if event["kind"] == "tool.proposed"
        ]
        results = [
            event
            for event in canonical["events"]
            if event["kind"] == "tool_result"
        ]
        self.assertEqual(1, len(proposals))
        self.assertEqual(1, len(results))
        self.assertEqual(
            proposals[0]["event_id"],
            results[0]["correlated_tool_proposal_event_id"],
        )
        self.assertEqual("unique_observed", results[0]["correlation_status"])
        self.assertTrue(
            all(
                event["observation_status"] == "observed"
                for event in canonical["events"]
            )
        )

    def test_is_deterministic_and_features_are_outcome_blind(self):
        failure = source_row(reward=0.0)
        success = copy.deepcopy(failure)
        success["reward"] = 1.0
        failure_canonical = canonicalize_cmu(failure)
        success_canonical = canonicalize_cmu(success)
        self.assertNotEqual(
            failure_canonical["trace_id"],
            success_canonical["trace_id"],
        )
        self.assertEqual(
            deterministic_attempt_features(failure_canonical),
            deterministic_attempt_features(success_canonical),
        )
        self.assertEqual(
            canonicalize_cmu(failure),
            canonicalize_cmu(copy.deepcopy(failure)),
        )

    def test_missing_and_duplicate_correlations_are_explicit(self):
        missing = source_row()
        missing["messages"][3]["tool_call_id"] = "unknown-call"
        canonical = canonicalize_cmu(missing)
        result = next(
            event
            for event in canonical["events"]
            if event["kind"] == "tool_result"
        )
        self.assertEqual("missing_proposal", result["correlation_status"])
        self.assertIn(
            "tool_result_proposal_correlation",
            canonical["loss_receipt"]["known_missing_fields"],
        )

        duplicate = source_row()
        duplicate["messages"][2]["tool_calls"].append(
            copy.deepcopy(duplicate["messages"][2]["tool_calls"][0])
        )
        duplicate_canonical = canonicalize_cmu(duplicate)
        duplicate_proposals = [
            event
            for event in duplicate_canonical["events"]
            if event["kind"] == "tool.proposed"
        ]
        self.assertEqual(
            "ambiguous_source_call_id",
            duplicate_proposals[-1]["correlation_status"],
        )
        self.assertIn(
            "unique_tool_call_correlation",
            duplicate_canonical["loss_receipt"]["known_missing_fields"],
        )

    def test_rejects_rows_that_require_guessing(self):
        invalid = source_row()
        invalid["pass"] = 0
        with self.assertRaisesRegex(CMUAdapterError, "pass"):
            canonicalize_cmu(invalid)
        invalid = source_row()
        invalid["messages"] = []
        with self.assertRaisesRegex(CMUAdapterError, "messages"):
            canonicalize_cmu(invalid)
        invalid = source_row()
        invalid["messages"][2]["tool_calls"] = {"not": "an array"}
        with self.assertRaisesRegex(CMUAdapterError, "tool_calls"):
            canonicalize_cmu(invalid)

    def test_group_key_keeps_model_and_task_passes_together(self):
        first = source_row(pass_number=1)
        second = source_row(source_id="row-2", pass_number=2)
        self.assertEqual(
            repeated_pass_group_key(first),
            repeated_pass_group_key(second),
        )
        other_model = copy.deepcopy(second)
        other_model["source_model"] = "other-model"
        self.assertNotEqual(
            repeated_pass_group_key(first),
            repeated_pass_group_key(other_model),
        )

    def test_aggregate_is_content_free_and_labels_independent_passes(self):
        rows = [
            source_row(
                source_id=f"row-{pass_number}",
                pass_number=pass_number,
                reward=1.0 if pass_number in {2, 4} else 0.0,
                error=pass_number in {1, 3},
            )
            for pass_number in range(1, 5)
        ]
        result = analyze_rows(rows)
        self.assertEqual(4, result["corpus"]["source_rows"])
        self.assertEqual(1, result["corpus"]["repeated_pass_groups"])
        self.assertEqual(1, result["corpus"]["complete_four_pass_groups"])
        self.assertEqual(1, result["corpus"]["mixed_outcome_groups"])
        self.assertEqual(
            3,
            result["observational_selection"][
                "ordered_failure_before_success_pairs"
            ],
        )
        self.assertTrue(
            result["validity"]["independent_passes_are_not_learning"]
        )
        serialized = str(result)
        self.assertNotIn("fixture-task", serialized)
        self.assertNotIn("synthetic task", serialized)
        self.assertNotIn("row-1", serialized)


if __name__ == "__main__":
    unittest.main()
