import copy
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from combined_evidence_matrix import (  # noqa: E402
    CombinedEvidenceError,
    build_matrix,
    render_markdown,
)


def inputs():
    return {
        "projection": {
            "schema_version": "projection",
            "fixture_corpus": {"canonical_events": 48},
            "ATIF_v1_7": {
                "canonical_event_identity_retention": 0.0,
                "canonical_parent_edge_retention": 0.0,
                "silent_drop_count": 0,
            },
            "OpenInference_OTel": {
                "canonical_event_identity_retention": 1.0,
                "canonical_parent_edge_retention": 1.0,
                "silent_drop_count": 0,
            },
        },
        "codetracebench": {
            "schema_version": "codetrace",
            "split_audit": {"verified_counts": {"test": 100}},
            "e1_signal_selection": {
                "arms": {
                    "uniform_random": {
                        "precision_mean": 0.40,
                        "precision_interval_95": [0.30, 0.55],
                    },
                    "structural_signal": {"precision": 0.54},
                    "trace_length": {"precision": 0.54},
                }
            },
            "e3_decisive_step_diagnosis": {
                "methods": {
                    "uniform_random": {"top1_accuracy": 0.10},
                    "reverse_chronology": {"top1_accuracy": 0.24},
                    "critical_stage_start_oracle": {
                        "top1_accuracy": 0.70
                    },
                }
            },
            "e4_eval_assertion_mutation": {
                "aggregate_by_assertion": {
                    "combined": {
                        "harmful_mutants": 100,
                        "harmful_mutant_kill_rate": 1.0,
                        "allowed_variation_false_positive_rate": 0.0,
                    }
                }
            },
        },
        "codetracebench_raw": {
            "schema_version": "codetrace-raw",
            "e3_factorial": {
                "eligible_traces": 35,
                "arms": {
                    "I0T0J0": {
                        "top1_accuracy": 0.286,
                        "top3_accuracy": 0.543,
                    },
                    "I1T1J1": {
                        "top1_accuracy": 0.171,
                        "top3_accuracy": 0.257,
                    },
                },
            },
            "e4_assertion_mutation": {
                "aggregate_by_assertion": {
                    "combined_raw_and_verifier": {
                        "harmful_mutants": 191,
                        "harmful_mutant_kill_rate": 0.969,
                        "allowed_variation_false_positive_rate": 0.486,
                    }
                }
            },
        },
        "mast": {
            "schema_version": "mast",
            "canonical_projection": {
                "aggregate": {
                    "source_lines": 1000,
                    "silently_dropped_lines": 0,
                }
            },
            "annotation_overlap": {
                "exact_trace_sha256_overlap": {
                    "finalized_human_vs_judge": 0
                },
                "human_vs_judge_scoring_status": "not_run",
            },
            "llm_judge_annotations": {"n": 100},
        },
        "wisp_governed": {
            "schema_version": "wisp",
            "authorized_counts": {
                "trajectories": 104,
                "fact_proposals": 0,
            },
            "denied_pre_ranking_candidate_matrix": {
                "counts": {
                    "wrong_subject": {
                        "history": 0,
                        "search": 0,
                        "proposals": 0,
                    }
                }
            },
            "latency": {
                "personal_history_page": {"p95_ms": 2.0},
                "proposal_queue": {"p95_ms": 2.0},
            },
        },
        "wisp_recovery": {
            "schema_version": "recovery",
            "corpora": {
                "wisp": {"constructor": {"matched_episodes": 89}},
                "share_codex_sparse": {
                    "constructor": {"matched_episodes": 31}
                },
            },
        },
        "cmu_access": {
            "schema_version": "cmu",
            "result": {
                "status": "requires_approval",
                "empirical_metrics_run": False,
            },
        },
        "otel_roundtrip": {
            "schema_version": "otel-roundtrip",
            "main_roundtrip": {
                "trace_ids_retained": 12,
                "stored_spans": 48,
                "parent_edges_retained": 34,
                "links_retained": 16,
            },
            "negative_controls_passed": True,
        },
        "memory_conformance": {
            "schema_version": "memory",
            "assertions": {"passed": 15, "total": 15, "failed": 0},
        },
        "agenttrace": {
            "schema_version": "agenttrace",
            "corpus": {"rows": 1400},
            "nl2bash_replay": {
                "historical_rows": 400,
                "executed_rows": 17,
                "equivalent_rows": 9,
            },
        },
        "native_history": {
            "schema_version": "native-history",
            "datasets": {
                "one": {},
                "two": {},
            },
            "classification": {"complete_harness_home": []},
        },
        "history_discovery": {
            "schema_version": "history-discovery",
            "classification": {
                "near_complete_home_state": ["one"],
                "real_research_trace_strata": ["one", "two"],
                "paired_trace_and_memory_strata": ["one", "two"],
            },
            "discovery_scale": {
                "top_repo_native_claude_files": 2362,
                "top_repo_native_codex_files": 329,
            },
            "security_observation": {
                "codex_repositories_with_auth_adjacent": 9,
            },
        },
    }


class CombinedEvidenceMatrixTests(unittest.TestCase):
    def test_builds_conservative_level_and_enterprise_decisions(self):
        matrix = build_matrix(inputs(), {"fixture": {"sha256": "x"}})
        self.assertEqual(
            "does_not_meet_gate",
            matrix["levels"]["L2_cheap_evidence_finding"]["status"],
        )
        self.assertEqual(
            "mixed_partial",
            matrix["levels"]["L3_diagnosis_and_eval_proposals"]["status"],
        )
        self.assertEqual(
            "synthetic_invariant_pass",
            matrix["levels"]["L5_temporal_memory"]["status"],
        )
        self.assertEqual(
            "not_supported",
            matrix["enterprise_questions"][
                "identify_missing_cloud_or_domain_skills"
            ]["status"],
        )
        self.assertFalse(
            matrix["architecture_decision"]["new_database_justified"]
        )
        self.assertFalse(
            matrix["architecture_decision"][
                "custom_embedding_model_justified"
            ]
        )

    def test_level_two_threshold_is_not_redefined_by_observed_result(self):
        source = inputs()
        source["codetracebench"]["e1_signal_selection"]["arms"][
            "structural_signal"
        ]["precision"] = 0.549
        matrix = build_matrix(source, {})
        evidence = matrix["levels"]["L2_cheap_evidence_finding"]["evidence"]
        self.assertAlmostEqual(0.149, evidence["structural_precision_lift"])
        self.assertEqual(0.15, evidence["required_absolute_lift"])
        self.assertEqual(
            "does_not_meet_gate",
            matrix["levels"]["L2_cheap_evidence_finding"]["status"],
        )

    def test_requires_every_claim_bearing_input_path(self):
        source = inputs()
        del source["mast"]["annotation_overlap"]
        with self.assertRaisesRegex(
            CombinedEvidenceError, "annotation_overlap"
        ):
            build_matrix(source, {})

    def test_markdown_does_not_emit_input_identifiers_or_content(self):
        source = inputs()
        source["wisp_governed"]["SECRET_CONTENT"] = "do not serialize"
        markdown = render_markdown(build_matrix(source, {}))
        self.assertNotIn("SECRET_CONTENT", markdown)
        self.assertNotIn("do not serialize", markdown)
        self.assertIn("Original enterprise questions", markdown)

    def test_input_is_not_mutated_and_output_is_deterministic(self):
        source = inputs()
        before = copy.deepcopy(source)
        first = build_matrix(source, {})
        second = build_matrix(source, {})
        self.assertEqual(before, source)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
