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
        "trace_memory_conformance": {
            "schema_version": "trace-memory",
            "native_trace_fidelity": {
                "records": 1602,
                "resolved_parent_edges": 1266,
                "unresolved_parent_edges": 0,
            },
            "memory_lifecycle": {
                "context_artifact_calls": 8,
                "joined_context_artifact_results": 8,
                "exact_write_to_later_read": 1,
                "interval_censored_version_gaps": 1,
                "reconstructable_edits": 2,
                "unreconstructable_edits": 0,
            },
            "negative_controls": {"all_passed": True},
            "raw_content_emitted": False,
        },
        "e2_retrieval": {
            "schema_version": "e2",
            "cohort": {
                "documents": 145,
                "eligible_queries": 99,
                "silver_positive_pairs": 87,
                "metadata_derived_hard_negative_pairs": 301,
            },
            "factorial": {
                "arms": {
                    "S0L0D0": {
                        "recall_at_20": 0.7323232323232324,
                        "exact_id_recall_at_20": 0.8,
                    },
                    "S1L0D1": {
                        "recall_at_20": 0.8181818181818182,
                        "recall_at_20_delta_vs_exact": 0.08585858585858586,
                        "recall_at_20_delta_95ci": [
                            0.03535353535353535,
                            0.13636363636363635,
                        ],
                        "exact_id_recall_at_20": 0.8944444444444445,
                    },
                }
            },
            "acceptance": {
                "human_label_gate_passed": False,
                "exact_identifier_no_regression": False,
                "joint_quality_rls_gate_passed": False,
                "custom_embedding_authorized": False,
                "aurora_replacement_authorized": False,
            },
            "runtime_authorization_evidence": {
                "all_denied_pre_ranking_candidates_zero": True,
                "joint_quality_and_rls_run": False,
                "same_corpus_as_quality_factorial": False,
            },
        },
        "e2_postgres_joint": {
            "schema_version": "e2-joint",
            "acceptance": {
                "same_candidate_local_postgres_quality_and_rls_gate_passed": True,
                "real_aurora_gate_passed": False,
                "concurrency_or_scale_gate_passed": False,
            },
            "postgresql": {
                "all_denied_pre_ranking_candidates_zero": True,
                "lifecycle_oracles": {"passed": True},
                "rollback": {"post_rollback_visible_rows": 0},
                "quality_against_silver_task_labels": {
                    "postgres_exact_pgvector": {
                        "recall_at_20": 0.6666666666666666
                    },
                    "postgres_hybrid_rrf": {
                        "recall_at_20": 0.6717171717171717
                    },
                },
                "client_observed_sequential_latency": {
                    "postgres_exact_pgvector": {"p50_ms": 3.017},
                    "postgres_hybrid_rrf_end_to_end": {
                        "p50_ms": 256.843
                    },
                },
            },
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
            "real_trace_transition_partial_pass",
            matrix["levels"]["L5_temporal_memory"]["status"],
        )
        self.assertEqual(
            "offline_silver_and_local_rls_partial_pass",
            matrix["levels"]["L4_semantic_candidate_retrieval"]["status"],
        )
        semantic = matrix["levels"]["L4_semantic_candidate_retrieval"][
            "evidence"
        ]
        self.assertEqual("S1L0D1", semantic["best_offline_arm"])
        self.assertAlmostEqual(
            0.08585858585858586,
            semantic["recall_at_20_lift_over_exact"],
        )
        self.assertFalse(semantic["human_label_gate_passed"])
        self.assertTrue(semantic["joint_local_postgres_gate_passed"])
        self.assertTrue(
            semantic["all_denied_pre_ranking_candidates_zero"]
        )
        self.assertEqual(0, semantic["post_rollback_visible_rows"])
        self.assertFalse(semantic["aurora_gate_passed"])
        temporal = matrix["levels"]["L5_temporal_memory"]["evidence"]
        self.assertEqual(1, temporal["real_exact_cross_session_continuities"])
        self.assertEqual(1, temporal["real_interval_censored_version_gaps"])
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
        self.assertTrue(
            matrix["levels"]["L7_to_L10"]["evidence"][
                "cmu_requirement_waived"
            ]
        )
        self.assertNotIn(
            "CMU",
            matrix["levels"]["L7_to_L10"]["decision"],
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
