import pathlib
import hashlib
import json
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import longitudinal_memory_corrected_model as corrected  # noqa: E402


class CorrectedLongitudinalMemoryModelTest(unittest.TestCase):
    def query(self):
        return {
            "artifact_name": "MEMORY.md",
            "project_context": "P-opaque",
            "valid_at": "2026-01-01T00:00:02Z",
            "known_at": "2026-01-01T00:00:02Z",
        }

    def evidence(self):
        return corrected.CorrectedEvidence(
            evidence_ref="E_0123456789abcdef",
            content="state",
            content_sha256=hashlib.sha256(b"state").hexdigest(),
            source_kind="read",
            authority_subject="subject-digest",
            project_context="project-digest",
            artifact_context="artifact-digest",
            revision_digest="b" * 64,
            known_at="2026-01-01T00:00:01Z",
            valid_from="2026-01-01T00:00:00Z",
            valid_to=None,
            interval_gap_known_at_cutoff=False,
        )

    def test_model_pack_hides_arm_and_latest_only_is_context_free(self):
        pack = corrected.serialize_state_pack(
            target_query=self.query(),
            evidence=[self.evidence()],
            view="latest_snapshot",
        )

        self.assertNotIn("arm", pack)
        self.assertEqual(
            {
                "memory_ref",
                "content",
                "context",
                "valid_time",
                "recorded_at",
                "source_refs",
            },
            set(pack["eligible_pre_cutoff_evidence"][0]),
        )
        item = pack["eligible_pre_cutoff_evidence"][0]
        self.assertEqual([], item["context"])
        self.assertIsNone(item["valid_time"])
        self.assertIsNone(item["recorded_at"])
        self.assertEqual([], item["source_refs"])

    def test_contextual_pack_exposes_complete_preregistered_time_fields(self):
        pack = corrected.serialize_state_pack(
            target_query=self.query(),
            evidence=[self.evidence()],
            view="temporal_ledger",
        )

        self.assertEqual(
            {
                "memory_ref",
                "content",
                "context",
                "valid_time",
                "recorded_at",
                "source_refs",
            },
            set(pack["eligible_pre_cutoff_evidence"][0]),
        )
        item = pack["eligible_pre_cutoff_evidence"][0]
        self.assertTrue(item["context"])
        self.assertEqual(
            "2026-01-01T00:00:01Z",
            item["recorded_at"],
        )
        self.assertEqual(
            "exact",
            item["valid_time"]["precision"],
        )

    def test_evidence_reference_is_opaque_and_independent_of_rank(self):
        original = corrected.opaque_evidence_ref(
            source_label="trace_commons",
            event_key="event-a",
            unit_key="unit-a",
            intervention_key="temporal",
            repeat_index=0,
            reference_hmac_key=b"test-reference-key-at-least-32-bytes",
        )
        after_unrelated_candidate = corrected.opaque_evidence_ref(
            source_label="trace_commons",
            event_key="event-a",
            unit_key="unit-a",
            intervention_key="temporal",
            repeat_index=0,
            reference_hmac_key=b"test-reference-key-at-least-32-bytes",
        )

        self.assertEqual(original, after_unrelated_candidate)
        self.assertRegex(original, r"^E_[0-9a-f]{24}$")
        self.assertNotIn("event-a", original)

    def test_memory_refs_are_rekeyed_per_unit_arm_run(self):
        arguments = {
            "source_label": "trace_commons",
            "event_key": "event-a",
            "unit_key": "unit-a",
            "reference_hmac_key": (
                b"test-reference-key-at-least-32-bytes"
            ),
        }

        temporal = corrected.opaque_evidence_ref(
            **arguments,
            intervention_key="temporal",
            repeat_index=0,
        )
        latest = corrected.opaque_evidence_ref(
            **arguments,
            intervention_key="latest",
            repeat_index=0,
        )
        repeated = corrected.opaque_evidence_ref(
            **arguments,
            intervention_key="temporal",
            repeat_index=1,
        )

        self.assertEqual(3, len({temporal, latest, repeated}))

    def test_primary_views_are_only_the_preregistered_treatments(self):
        self.assertEqual(
            (
                "latest_snapshot",
                "temporal_ledger",
                "temporal_plus_released_dream",
            ),
            corrected.STATE_VIEWS,
        )

    def test_decision_item_field_set_is_identical_across_arms(self):
        field_sets = []
        for view in corrected.STATE_VIEWS:
            pack = corrected.serialize_state_pack(
                target_query=self.query(),
                evidence=[self.evidence()],
                view=view,
            )
            field_sets.append(
                set(pack["eligible_pre_cutoff_evidence"][0])
            )

        self.assertTrue(
            all(fields == field_sets[0] for fields in field_sets)
        )

    def test_decision_pack_has_no_arm_source_unit_rank_or_gold_fields(self):
        pack = corrected.serialize_state_pack(
            target_query=self.query(),
            evidence=[self.evidence()],
            view="temporal_ledger",
        )
        serialized = json.dumps(pack, sort_keys=True).casefold()

        for forbidden in (
            '"arm"',
            "source_label",
            "source_family",
            "unit_id",
            "retrieval_rank",
            "gold_label",
            "target_result",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_target_result_descendants_and_future_never_serialize(self):
        for forbidden in (
            "target_result",
            "descendant_content",
            "future_material",
        ):
            query = {**self.query(), forbidden: "must-not-pass"}
            with self.assertRaises(corrected.CorrectedProtocolError):
                corrected.serialize_state_pack(
                    target_query=query,
                    evidence=[self.evidence()],
                    view="temporal_ledger",
                )

    def test_execution_order_is_frozen_seed_randomized(self):
        first = corrected.frozen_intervention_order(
            unit_key="unit-a",
            seed=20260730,
        )
        second = corrected.frozen_intervention_order(
            unit_key="unit-a",
            seed=20260730,
        )
        another = corrected.frozen_intervention_order(
            unit_key="unit-b",
            seed=20260730,
        )

        self.assertEqual(first, second)
        self.assertEqual(set(corrected.STATE_VIEWS), set(first))
        self.assertNotEqual(first, another)

    def test_state_decision_rejects_plain_json_without_native_tool(self):
        response = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {
                                "decision": "abstain",
                                "memory_ref": None,
                                "epistemic_status": "insufficient",
                                "reason": "no_eligible_evidence",
                            }
                        )
                    },
                }
            ]
        }

        with self.assertRaises(corrected.CorrectedProtocolError):
            corrected.parse_native_state_decision(response)

    def test_state_decision_accepts_exactly_one_named_native_tool(self):
        expected = {
            "decision": "select",
            "memory_ref": "E_0123456789abcdef01234567",
            "epistemic_status": "resolved",
            "reason": "unique_supported_state",
        }
        response = {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "submit_state_decision",
                                    "arguments": json.dumps(expected),
                                },
                            }
                        ],
                    },
                }
            ]
        }

        self.assertEqual(
            expected,
            corrected.parse_native_state_decision(response),
        )

    def test_budget_drop_is_retrieval_failure_not_correct_abstention(self):
        exact = self.evidence()
        result = corrected.evaluate_state_decision(
            oracle_pre_cutoff=[exact],
            arm_pre_budget=[exact],
            supplied_post_budget=[],
            gold_epistemic_status="resolved",
            acceptable_content_sha256={exact.content_sha256},
            decision={
                "decision": "abstain",
                "memory_ref": None,
                "epistemic_status": "insufficient",
                "reason": "no_eligible_evidence",
            },
        )

        self.assertTrue(result["oracle_exact_available"])
        self.assertTrue(result["arm_exact_available_pre_budget"])
        self.assertFalse(result["exact_retained_post_budget"])
        self.assertFalse(result["retrieval_stage_success"])
        self.assertFalse(result["task_decision_correct"])
        self.assertIsNone(result["reasoning_correct_given_retained_exact"])

    def test_true_conflict_abstention_scores_correctly(self):
        result = corrected.evaluate_state_decision(
            oracle_pre_cutoff=[],
            arm_pre_budget=[],
            supplied_post_budget=[],
            gold_epistemic_status="conflict",
            acceptable_content_sha256=set(),
            decision={
                "decision": "abstain",
                "memory_ref": None,
                "epistemic_status": "conflict",
                "reason": "incompatible_overlap",
            },
        )

        self.assertTrue(result["task_decision_correct"])
        self.assertTrue(result["epistemic_status_correct"])

    def test_later_observation_agreement_is_not_primary_correctness(self):
        item = self.evidence()
        result = corrected.evaluate_state_decision(
            oracle_pre_cutoff=[item],
            arm_pre_budget=[item],
            supplied_post_budget=[item],
            gold_epistemic_status="last_observed_only",
            acceptable_content_sha256={item.content_sha256},
            later_observation_content_sha256=item.content_sha256,
            decision={
                "decision": "select",
                "memory_ref": item.evidence_ref,
                "epistemic_status": "resolved",
                "reason": "unique_supported_state",
            },
        )

        self.assertTrue(result["later_observation_agreement"])
        self.assertFalse(result["task_decision_correct"])
        self.assertFalse(result["epistemic_status_correct"])

    def test_packing_drops_only_whole_proposals_and_preserves_base(self):
        base = self.evidence()
        proposal = corrected.CorrectedEvidence(
            **{
                **base.__dict__,
                "evidence_ref": "E_abcdefabcdefabcdefabcdef",
                "content": "proposal",
                "content_sha256": hashlib.sha256(
                    b"proposal"
                ).hexdigest(),
            }
        )

        packed, receipt = corrected.pack_whole_evidence(
            base_evidence=[base],
            proposal_evidence=[proposal],
            token_cost_by_ref={
                base.evidence_ref: 7,
                proposal.evidence_ref: 5,
            },
            token_budget=10,
        )

        self.assertEqual([base], packed)
        self.assertEqual([proposal.evidence_ref], receipt["dropped_refs"])
        self.assertEqual(7, receipt["tokens_used"])
        self.assertEqual(base.content, packed[0].content)

    def test_over_budget_required_base_fails_before_inference(self):
        base = self.evidence()

        with self.assertRaises(corrected.CorrectedProtocolError):
            corrected.pack_whole_evidence(
                base_evidence=[base],
                proposal_evidence=[],
                token_cost_by_ref={base.evidence_ref: 11},
                token_budget=10,
            )


if __name__ == "__main__":
    unittest.main()
