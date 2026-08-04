import importlib.util
import json
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "longitudinal_memory_local_model.py"
)
SPEC = importlib.util.spec_from_file_location(
    "longitudinal_memory_local_model",
    MODULE_PATH,
)
local = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = local
SPEC.loader.exec_module(local)


def evidence(
    ref,
    content,
    digest,
    project="project-a",
    artifact="artifact-a",
):
    return local.EvidenceItem(
        evidence_ref=ref,
        canonical_content=content,
        content_sha256=digest,
        observed_at="2026-01-01T00:00:00+00:00",
        source_kind="read",
        project_key=project,
        artifact_key=artifact,
    )


def unit():
    exact = evidence("E001", "earlier content", "digest-exact")
    wrong = evidence(
        "E002",
        "wrong project",
        "digest-wrong",
        project="project-b",
    )
    return local.ModelUnit(
        unit_id="unit-a",
        source_label="fixture",
        target_query={
            "artifact_path": "/Users/private/project/MEMORY.md",
            "target_canary": "query-only",
        },
        evidence_by_arm={
            "no_memory": (),
            "verbatim": (exact,),
            "latest_only": (wrong,),
            "contextual_bitemporal": (exact,),
            "proposal_only_dream": (exact,),
        },
        label=local.EvaluationLabel(
            target_content_sha256="digest-exact",
            target_project_key="project-a",
            interval_censored_change=False,
        ),
    )


class LongitudinalMemoryLocalModelTest(unittest.TestCase):
    def test_model_pack_never_contains_evaluator_only_target_label(self):
        value = unit()
        for arm in local.ARMS:
            pack = local.model_pack(value, arm)
            serialized = json.dumps(pack)
            self.assertNotIn("digest-exact", serialized)
            self.assertNotIn("interval_censored_change", serialized)
            self.assertNotIn("target_content", serialized)

    def test_arm_surfaces_are_distinct_and_cutoff_safe(self):
        value = unit()
        self.assertEqual(
            [],
            local.model_pack(value, "no_memory")[
                "eligible_pre_cutoff_evidence"
            ],
        )
        verbatim = local.model_pack(value, "verbatim")[
            "eligible_pre_cutoff_evidence"
        ][0]
        self.assertEqual(
            {"evidence_ref", "content"},
            set(verbatim),
        )
        contextual = local.model_pack(
            value,
            "contextual_bitemporal",
        )["eligible_pre_cutoff_evidence"][0]
        self.assertIn("observed_at", contextual)
        self.assertIn("project_context", contextual)

    def test_parse_decision_enforces_closed_schema_and_refs(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "decision": "select",
                                "evidence_ref": "E001",
                                "reason": "exact_supported",
                            }
                        )
                    }
                }
            ]
        }
        parsed = local.parse_decision(response)
        self.assertEqual("select", parsed.decision)
        tool_parsed = local.parse_decision(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "submit_state_decision",
                                        "arguments": json.dumps(
                                            {
                                                "decision": "select",
                                                "evidence_ref": "E001",
                                                "reason": "exact_supported",
                                            }
                                        ),
                                    }
                                }
                            ],
                        }
                    }
                ]
            }
        )
        self.assertEqual("E001", tool_parsed.evidence_ref)
        normalized_abstention = local.parse_decision(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision": "abstain",
                                    "reason": "insufficient",
                                }
                            )
                        }
                    }
                ]
            }
        )
        self.assertIsNone(normalized_abstention.evidence_ref)
        with self.assertRaises(local.LocalModelExperimentError):
            local.parse_decision(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "decision": "select",
                                        "evidence_ref": "E001",
                                        "reason": "exact_supported",
                                        "extra": "forbidden",
                                    }
                                )
                            }
                        }
                    ]
                }
            )

    def test_evaluator_scores_exact_stale_context_and_abstention(self):
        value = unit()
        exact = local.evaluate_decision(
            value,
            "contextual_bitemporal",
            local.ParsedDecision(
                decision="select",
                evidence_ref="E001",
                reason="exact_supported",
            ),
        )
        self.assertTrue(exact["selected_exact"])
        wrong = local.evaluate_decision(
            value,
            "latest_only",
            local.ParsedDecision(
                decision="select",
                evidence_ref="E002",
                reason="exact_supported",
            ),
        )
        self.assertTrue(wrong["selected_stale"])
        self.assertTrue(wrong["selected_wrong_context"])
        abstain = local.evaluate_decision(
            value,
            "no_memory",
            local.ParsedDecision(
                decision="abstain",
                evidence_ref=None,
                reason="insufficient",
            ),
        )
        self.assertTrue(abstain["correct_abstention"])

    def test_non_loopback_endpoint_is_rejected(self):
        for endpoint in (
            "https://api.example.com",
            "http://10.0.0.4:8765",
            "http://user:password@127.0.0.1:8765",
        ):
            with self.assertRaises(local.LocalModelExperimentError):
                local.require_loopback_endpoint(endpoint)
        self.assertEqual(
            "http://127.0.0.1:8765",
            local.require_loopback_endpoint(
                "http://127.0.0.1:8765/"
            ),
        )

    def test_budget_drops_whole_items_then_truncates_last(self):
        class CharacterCounter:
            def count(self, text):
                return len(text)

        value = unit()
        many = tuple(
            evidence(
                f"E{index:03d}",
                "content-" + ("x" * 300),
                f"digest-{index}",
            )
            for index in range(1, 9)
        )
        value = local.ModelUnit(
            unit_id=value.unit_id,
            source_label=value.source_label,
            target_query=value.target_query,
            evidence_by_arm={
                **value.evidence_by_arm,
                "contextual_bitemporal": many,
            },
            label=value.label,
        )
        pack, receipt = local.budget_model_pack(
            value,
            "contextual_bitemporal",
            CharacterCounter(),
            token_budget=1100,
            candidate_limit=5,
        )
        self.assertLessEqual(
            len(local.stable_json(pack)),
            1100,
        )
        self.assertEqual(3, receipt["dropped_for_candidate_limit"])
        self.assertGreater(receipt["dropped_for_token_budget"], 0)
        self.assertTrue(receipt["last_item_utf8_tail_truncated"])

    def test_aggregate_stability_uses_complete_valid_unit_arms(self):
        receipts = []
        for run_index in range(2):
            receipts.append(
                {
                    "unit_id": "u1",
                    "arm": "no_memory",
                    "status": "valid",
                    "selected_exact": False,
                    "selected_stale": False,
                    "selected_wrong_context": False,
                    "correct_abstention": True,
                    "valid_reference": True,
                    "elapsed_ms": 10,
                    "prompt_tokens": 5,
                    "completion_tokens": 2,
                    "normalized_decision_sha256": "same",
                }
            )
        aggregate = local.aggregate_runs(
            receipts,
            independent_runs=2,
        )
        self.assertEqual(
            1.0,
            aggregate["five_run_stability"]["rate"],
        )

    def test_budget_aggregate_is_content_free(self):
        rows = [
            {
                "arm": "verbatim",
                "token_budget": 2048,
                "final_pack_tokens": 1900,
                "last_item_utf8_tail_truncated": True,
                "dropped_for_candidate_limit": 2,
                "dropped_for_token_budget": 1,
            },
            {
                "arm": "verbatim",
                "token_budget": 2048,
                "final_pack_tokens": 1200,
                "last_item_utf8_tail_truncated": False,
                "dropped_for_candidate_limit": 0,
                "dropped_for_token_budget": 0,
            },
        ]
        aggregate = local.aggregate_budgets(rows)["verbatim"]
        self.assertEqual(2, aggregate["packs"])
        self.assertEqual(1, aggregate["last_item_truncated"])
        self.assertEqual(2, aggregate["items_dropped_for_candidate_limit"])


if __name__ == "__main__":
    unittest.main()
