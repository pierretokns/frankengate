import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "longitudinal_memory_local_finalize.py"
)
SPEC = importlib.util.spec_from_file_location(
    "longitudinal_memory_local_finalize",
    MODULE_PATH,
)
finalize = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC.loader.exec_module(finalize)


def _budget():
    return {
        "token_budget": 2048,
        "candidate_limit": 5,
        "original_candidates": 0,
        "included_candidates": 0,
        "dropped_for_candidate_limit": 0,
        "dropped_for_token_budget": 0,
        "last_item_utf8_tail_truncated": False,
        "final_pack_tokens": 100,
    }


def _valid_events():
    budget = _budget()
    return [
        {
            "event": "model_request",
            "unit_id": "a" * 64,
            "source_label": "trace_commons",
            "arm": "no_memory",
            "run_index": 0,
            "system_prompt": "select state",
            "pack": {
                "arm": "no_memory",
                "eligible_pre_cutoff_evidence": [],
                "evidence_budget_receipt": budget,
            },
            "budget_receipt": budget,
        },
        {
            "event": "model_response",
            "response": {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "submit_state_decision",
                                        "arguments": "{}",
                                    }
                                }
                            ]
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                },
            },
        },
        {
            "event": "parsed_decision",
            "parsed_decision": {
                "decision": "abstain",
                "evidence_ref": None,
                "reason": "insufficient",
            },
            "evaluation": {
                "reason": "insufficient",
                "selected_exact": False,
                "selected_stale": False,
                "selected_wrong_context": False,
                "correct_abstention": True,
                "valid_reference": True,
                "exact_evidence_available": False,
                "abstained": True,
            },
        },
    ]


class LongitudinalMemoryLocalFinalizeTest(unittest.TestCase):
    def test_source_aggregate_and_stability_are_identifier_free(self):
        rows = []
        for run_index in range(2):
            rows.append(
                {
                    "unit_id": "a" * 64,
                    "source": "trace_commons",
                    "arm": "no_memory",
                    "run_index": run_index,
                    "status": "valid",
                    "decision_sha256": "same",
                    "behavior_sha256": "same-behavior",
                    "decision": "abstain",
                    "reason": "insufficient",
                    "selected_exact": False,
                    "selected_stale": False,
                    "selected_wrong_context": False,
                    "correct_abstention": True,
                    "valid_reference": True,
                    "exact_evidence_available": False,
                    "abstained": True,
                    "exact_decision_correct": True,
                    "prompt_tokens": 20,
                    "completion_tokens": 5,
                    "response_transport": "native_tool",
                }
            )
        aggregate = finalize.aggregate_source_arms(rows)
        self.assertEqual(
            1.0,
            aggregate["trace_commons"]["no_memory"][
                "correct_abstention"
            ]["rate"],
        )
        stability = finalize.aggregate_stability(rows, 2)
        self.assertEqual(
            1.0,
            stability["trace_commons"]["no_memory"][
                "strict_valid_and_behaviorally_stable"
            ]["rate"],
        )
        serialized = json.dumps(
            {"aggregate": aggregate, "stability": stability}
        )
        self.assertNotIn("a" * 64, serialized)

    def test_attempt_reader_keeps_content_out_of_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attempt.jsonl"
            events = [
                {
                    "event": "model_request",
                    "unit_id": "a" * 64,
                    "source_label": "trace_commons",
                    "arm": "verbatim",
                    "run_index": 0,
                    "system_prompt": "select state",
                    "pack": {
                        "arm": "verbatim",
                        "content": "person@example.com",
                        "evidence_budget_receipt": {
                            "token_budget": 2048,
                            "candidate_limit": 5,
                            "original_candidates": 0,
                            "included_candidates": 0,
                            "final_pack_tokens": 100,
                            "last_item_utf8_tail_truncated": False,
                            "dropped_for_candidate_limit": 0,
                            "dropped_for_token_budget": 0,
                        },
                    },
                    "budget_receipt": {
                        "token_budget": 2048,
                        "candidate_limit": 5,
                        "original_candidates": 0,
                        "included_candidates": 0,
                        "final_pack_tokens": 100,
                        "last_item_utf8_tail_truncated": False,
                        "dropped_for_candidate_limit": 0,
                        "dropped_for_token_budget": 0,
                    },
                },
                {
                    "event": "model_response",
                    "response": {
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 4,
                        }
                    },
                },
                {
                    "event": "parsed_decision",
                    "parsed_decision": {
                        "decision": "abstain",
                        "evidence_ref": None,
                        "reason": "insufficient",
                    },
                    "evaluation": {
                        "reason": "insufficient",
                        "selected_exact": False,
                        "selected_stale": False,
                        "selected_wrong_context": False,
                        "correct_abstention": True,
                        "valid_reference": True,
                        "exact_evidence_available": False,
                        "abstained": True,
                    },
                },
            ]
            path.write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            receipt = finalize.read_attempt(path)
            serialized = json.dumps(receipt)
            self.assertNotIn("person@example.com", serialized)
            self.assertNotIn('"pack":', serialized)

    def test_incomplete_terminal_event_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attempt.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "event": "model_request",
                        "unit_id": "a" * 64,
                        "source_label": "trace_commons",
                        "arm": "no_memory",
                        "run_index": 0,
                        "budget_receipt": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(finalize.FinalizationError):
                finalize.read_attempt(path)

    def test_summary_contains_only_aggregate_surfaces(self):
        rate = {"numerator": 1, "denominator": 1, "rate": 1.0}
        arm_result = {
            "attempts": 1,
            "valid": rate,
            "exact_decision_correct": rate,
            "selected_exact": rate,
            "selected_stale": rate,
            "selected_wrong_context": rate,
            "correct_abstention": rate,
            "mean_elapsed_ms": 12.5,
        }
        source_arm = {
            "attempts": 1,
            "valid": rate,
            "exact_decision_correct": rate,
            "selected_exact": rate,
            "selected_stale": rate,
            "selected_wrong_context": rate,
            "correct_abstention": rate,
        }
        result = {
            "execution": {
                "model_id_declared_by_manifest": "model",
                "model_revision_declared_by_manifest": "b" * 40,
                "units_executed": 2,
                "attempts": 10,
                "repeated_invocations_per_unit_arm": 1,
                "max_completion_tokens": 256,
                "source_unit_counts": {
                    source: 1 for source in finalize.EXPECTED_SOURCES
                },
                "raw_audit_files_verified": 10,
                "raw_audit_set_sha256": "c" * 64,
            },
            "overall": {
                "arms": {
                    arm: arm_result for arm in finalize.ARMS
                }
            },
            "source_stratified": {
                source: {
                    arm: source_arm for arm in finalize.ARMS
                }
                for source in finalize.EXPECTED_SOURCES
            },
            "source_stratified_five_run_stability": {
                source: {
                    arm: {
                        "strict_valid_and_behaviorally_stable": rate,
                        "conditional_behavioral": rate,
                        "conditional_full_output": rate,
                        "all_repeats_valid": rate,
                    }
                    for arm in finalize.ARMS
                }
                for source in finalize.EXPECTED_SOURCES
            },
            "paired_arm_behavior_agreement": {
                f"{left}__{right}": rate
                for index, left in enumerate(finalize.ARMS)
                for right in finalize.ARMS[index + 1 :]
            },
            "evidence_budget": {
                arm: {
                    "packs": 2,
                    "token_budget": 2048,
                    "minimum_pack_tokens": 100,
                    "maximum_pack_tokens": 200,
                    "last_item_truncated": 0,
                    "items_dropped_for_candidate_limit": 0,
                    "items_dropped_for_token_budget": 0,
                }
                for arm in finalize.ARMS
            },
            "result_sha256": "d" * 64,
        }
        summary = finalize.render_summary(result)
        self.assertIn("Source-stratified results", summary)
        self.assertIn(
            "authorized internal full-fidelity",
            summary.lower(),
        )
        self.assertNotIn("person@example.com", summary)

    def test_attempt_census_requires_every_unit_arm_run(self):
        rows = []
        for source in finalize.EXPECTED_SOURCES:
            for arm in finalize.ARMS:
                for run_index in range(2):
                    rows.append(
                        {
                            "source": source,
                            "unit_id": (
                                "a" * 64
                                if source == "trace_commons"
                                else "b" * 64
                            ),
                            "arm": arm,
                            "run_index": run_index,
                        }
                    )
        finalize.validate_attempt_census(
            rows,
            independent_runs=2,
            expected_source_counts={
                source: 1 for source in finalize.EXPECTED_SOURCES
            },
        )
        rows.pop()
        with self.assertRaises(finalize.FinalizationError):
            finalize.validate_attempt_census(
                rows,
                independent_runs=2,
                expected_source_counts={
                    source: 1
                    for source in finalize.EXPECTED_SOURCES
                },
            )

    def test_attempt_reader_rejects_string_boolean_and_unknown_reason(self):
        for field, value in (
            ("selected_exact", "false"),
            ("reason", "person@example.com"),
        ):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as directory:
                    path = pathlib.Path(directory) / "attempt.jsonl"
                    events = _valid_events()
                    events[2]["evaluation"][field] = value
                    path.write_text(
                        "".join(
                            json.dumps(event) + "\n"
                            for event in events
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaises(
                        finalize.FinalizationError
                    ):
                        finalize.read_attempt(path)

    def test_attempt_reader_rejects_negative_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attempt.jsonl"
            events = _valid_events()
            events[1]["response"]["usage"]["completion_tokens"] = -1
            path.write_text(
                "".join(
                    json.dumps(event) + "\n" for event in events
                ),
                encoding="utf-8",
            )
            with self.assertRaises(finalize.FinalizationError):
                finalize.read_attempt(path)

    def test_intervention_must_match_across_repeats(self):
        first = {
            "unit_id": "a" * 64,
            "arm": "no_memory",
            "budget_receipt": _budget(),
            "intervention_sha256": "1" * 64,
        }
        second = {
            **first,
            "intervention_sha256": "2" * 64,
        }
        with self.assertRaises(finalize.FinalizationError):
            finalize.unique_budgets([first, second])

    def test_pairwise_agreement_is_content_free(self):
        rows = []
        for arm in finalize.ARMS:
            rows.append(
                {
                    "source": "trace_commons",
                    "unit_id": "a" * 64,
                    "run_index": 0,
                    "arm": arm,
                    "status": "valid",
                    "behavior_sha256": (
                        "same" if arm != "no_memory" else "different"
                    ),
                }
            )
        result = finalize.aggregate_pairwise_arm_agreement(rows)
        self.assertEqual(
            1.0,
            result["verbatim__latest_only"]["rate"],
        )
        self.assertNotIn("a" * 64, json.dumps(result))

    def test_base_self_hash_is_verified(self):
        value = {
            "schema_version": "x",
            "result_sha256": "0" * 64,
        }
        with self.assertRaises(finalize.FinalizationError):
            finalize._validate_base_self_hash(value)


if __name__ == "__main__":
    unittest.main()
