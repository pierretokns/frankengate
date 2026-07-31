#!/usr/bin/env python3
"""Compose independent trace-intelligence arms into one claim ledger.

This module does not pool heterogeneous scores. It evaluates whether the
prerequisites for each Frankengate research level are satisfied, failed, or
still missing, while retaining the decisive metric from each independent arm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-combined-evidence-matrix-v9"
REQUIRED_RESULTS = {
    "projection": "canonical-projection-e0-conformance-2026-07-30.json",
    "atif_rl_roundtrip": "atif-rl-roundtrip-2026-07-30.json",
    "matm_skill_retrieval": "matm-trace-skill-retrieval-2026-08-02.json",
    "codetracebench": "codetracebench-manifest-e1-e3-e4-2026-07-30.json",
    "codetracebench_raw": "codetracebench-raw-e3-e4-factorial-2026-07-30.json",
    "mast": "mast_multiagent_empirical-2026-07-30.json",
    "wisp_governed": "wisp-governed-postgres-benchmark-2026-07-30.json",
    "wisp_recovery": "wisp-share-codex-canonical-bounded-recovery-2026-07-30.json",
    "otel_roundtrip": "otel-collector-roundtrip-e0-2026-07-30.json",
    "memory_conformance": "bitemporal-memory-conformance-2026-07-30.json",
    "trace_memory_conformance": (
        "trace-commons-memory-conformance-2026-07-30.json"
    ),
    "natural_memory_factorial": (
        "natural-trace-memory-factorial-2026-08-02-r2.json"
    ),
    "e2_retrieval": (
        "codetracebench-e2-authorized-retrieval-factorial-2026-07-30.json"
    ),
    "e2_postgres_joint": (
        "codetracebench-e2-postgres-joint-retrieval-2026-07-30.json"
    ),
    "agenttrace": "agenttrace-nl2bash-replay-audit-2026-07-30.json",
    "native_history": "public-native-history-fidelity-2026-07-30.json",
    "history_discovery": "public-agent-history-discovery-2026-07-30.json",
    "trace2skill_stage0": "trace2skill-governed-stage0-2026-07-30.json",
    "skill_optimization_meta": (
        "skill-optimization-meta-analysis-2026-08-02.json"
    ),
    "skill_harness_transfer": (
        "model-harness-transfer-native-tool-2026-07-31.json"
    ),
    "skill_cross_harness_transfer": (
        "model-harness-transfer-llama-openai-vs-ollama-2026-07-31.json"
    ),
    "skill_qwen_native": (
        "natural-trace-skill-protocol-ollama-native-qwen3-4b-2026-07-31.json"
    ),
    "gepa_protocol": "gepa-native-tool-protocol-2026-08-02-r2.json",
    "statebench_sql": "statebench-finance-sql-fixture-smoke-2026-07-30.json",
    "skill_release": "governed-skill-release-lifecycle-2026-07-30.json",
    "trace_commons_attestation": (
        "trace-commons-source-attestation-2026-08-02.json"
    ),
    "trace_commons_full": (
        "trace-commons-full-content-minimized-analysis-2026-08-02.json"
    ),
    "trace_commons_repro": (
        "trace-commons-analysis-reproducibility-2026-08-02.json"
    ),
}


class CombinedEvidenceError(ValueError):
    pass


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require(mapping: dict[str, Any], *path: str) -> Any:
    value: Any = mapping
    for part in path:
        if not isinstance(value, dict) or part not in value:
            raise CombinedEvidenceError(
                "missing required result path " + ".".join(path)
            )
        value = value[part]
    return value


def load_results(result_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    values: dict[str, Any] = {}
    receipts: dict[str, Any] = {}
    for name, filename in REQUIRED_RESULTS.items():
        path = result_dir / filename
        try:
            raw = path.read_bytes()
            value = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise CombinedEvidenceError(f"cannot load {path}: {exc}") from exc
        if not isinstance(value, dict) or not value.get("schema_version"):
            raise CombinedEvidenceError(f"{path}: schema_version is required")
        values[name] = value
        receipts[name] = {
            "filename": filename,
            "schema_version": value["schema_version"],
            "sha256": _sha256_bytes(raw),
        }
    return values, receipts


def build_matrix(
    results: dict[str, Any],
    receipts: dict[str, Any],
) -> dict[str, Any]:
    projection = results["projection"]
    atif_rl_roundtrip = results["atif_rl_roundtrip"]
    matm_skill_retrieval = results["matm_skill_retrieval"]
    codetrace = results["codetracebench"]
    codetrace_raw = results["codetracebench_raw"]
    mast = results["mast"]
    wisp = results["wisp_governed"]
    recovery = results["wisp_recovery"]
    otel_roundtrip = results["otel_roundtrip"]
    memory = results["memory_conformance"]
    trace_memory = results["trace_memory_conformance"]
    natural_memory = results["natural_memory_factorial"]
    e2_retrieval = results["e2_retrieval"]
    e2_joint = results["e2_postgres_joint"]
    agenttrace = results["agenttrace"]
    native_history = results["native_history"]
    history_discovery = results["history_discovery"]
    trace2skill_stage0 = results["trace2skill_stage0"]
    skill_optimization_meta = results["skill_optimization_meta"]
    skill_harness_transfer = results["skill_harness_transfer"]
    skill_cross_harness_transfer = results["skill_cross_harness_transfer"]
    skill_qwen_native = results["skill_qwen_native"]
    gepa_protocol = results["gepa_protocol"]
    statebench_sql = results["statebench_sql"]
    skill_release = results["skill_release"]
    trace_commons_attestation = results.get("trace_commons_attestation")
    trace_commons_full = results.get("trace_commons_full")
    trace_commons_repro = results["trace_commons_repro"]

    trace_commons_attestation_passed = bool(
        trace_commons_attestation
        and trace_commons_attestation.get("attestation") == "passed"
    )
    trace_commons_s0 = (
        trace_commons_full.get("S0_metadata", {})
        if trace_commons_full
        else {}
    )
    trace_commons_s4 = (
        trace_commons_full.get("S4_temporal_episode_candidates", {})
        if trace_commons_full
        else {}
    )
    trace_commons_s6 = (
        trace_commons_full.get("S6_proposal_records", {})
        if trace_commons_full
        else {}
    )

    atif = _require(projection, "ATIF_v1_7")
    otel = _require(projection, "OpenInference_OTel")
    rl_family = _require(
        atif_rl_roundtrip, "families", "matm_alfworld_rl_environment"
    )
    coding_family = _require(
        atif_rl_roundtrip, "families", "wisp_claude_code_tool_rich"
    )
    rl_measurement = _require(rl_family, "measurement")
    coding_measurement = _require(coding_family, "measurement")
    rl_atif = _require(rl_measurement, "formats", "ATIF_v1_7_profiled")
    rl_otel = _require(
        rl_measurement, "formats", "OpenInference_OTel_profiled"
    )
    coding_atif = _require(
        coding_measurement, "formats", "ATIF_v1_7_profiled"
    )
    coding_otel = _require(
        coding_measurement, "formats", "OpenInference_OTel_profiled"
    )
    e1_arms = _require(codetrace, "e1_signal_selection", "arms")
    random_arm = _require(e1_arms, "uniform_random")
    structural_arm = _require(e1_arms, "structural_signal")
    raw_e3_arms = _require(codetrace_raw, "e3_factorial", "arms")
    raw_e4_combined = _require(
        codetrace_raw,
        "e4_assertion_mutation",
        "aggregate_by_assertion",
        "combined_raw_and_verifier",
    )
    mast_projection = _require(mast, "canonical_projection", "aggregate")
    mast_overlap = _require(mast, "annotation_overlap")
    authority_matrix = _require(
        wisp, "denied_pre_ranking_candidate_matrix", "counts"
    )
    latency = _require(wisp, "latency")

    structural_lift_over_random_mean = (
        float(structural_arm["precision"])
        - float(random_arm["precision_mean"])
    )
    structural_exceeds_random_interval = (
        float(structural_arm["precision"])
        > float(random_arm["precision_interval_95"][1])
    )
    all_denied_zero = all(
        all(int(value) == 0 for value in counts.values())
        for counts in authority_matrix.values()
    )
    skill_transfer_models = sorted(
        {
            str(model["model_id"])
            for model in _require(skill_harness_transfer, "models")
        }
    )
    skill_transfer_harnesses = sorted(
        {
            str(model["harness_id"])
            for model in (
                _require(skill_harness_transfer, "models")
                + _require(skill_cross_harness_transfer, "models")
            )
        }
    )
    qwen_native_variants = _require(skill_qwen_native, "variant_results")

    levels = {
        "L0_evidence_conformance": {
            "status": "real_roundtrip_partial_pass",
            "decision": (
                "keep one governed canonical DAG; ATIF and OTel remain "
                "receipted projections"
            ),
            "evidence": {
                "governed_fixture_events": _require(
                    projection, "fixture_corpus", "canonical_events"
                ),
                "atif_event_identity_retention": atif[
                    "canonical_event_identity_retention"
                ],
                "atif_parent_edge_retention": atif[
                    "canonical_parent_edge_retention"
                ],
                "atif_silent_drops": atif["silent_drop_count"],
                "otel_event_identity_retention": otel[
                    "canonical_event_identity_retention"
                ],
                "otel_parent_edge_retention": otel[
                    "canonical_parent_edge_retention"
                ],
                "otel_silent_drops": otel["silent_drop_count"],
                "mast_source_lines": mast_projection["source_lines"],
                "mast_silent_line_drops": mast_projection[
                    "silently_dropped_lines"
                ],
                "collector_trace_ids_retained": _require(
                    otel_roundtrip, "main_roundtrip", "trace_ids_retained"
                ),
                "collector_spans_retained": _require(
                    otel_roundtrip, "main_roundtrip", "stored_spans"
                ),
                "collector_parent_edges_retained": _require(
                    otel_roundtrip, "main_roundtrip", "parent_edges_retained"
                ),
                "collector_links_retained": _require(
                    otel_roundtrip, "main_roundtrip", "links_retained"
                ),
                "collector_negative_controls_passed": _require(
                    otel_roundtrip, "negative_controls_passed"
                ),
                "trace_commons_reproduction_passed": _require(
                    trace_commons_repro, "all_passed"
                ),
                "trace_commons_reproduction_metrics_compared": _require(
                    trace_commons_repro, "metrics_compared"
                ),
                "rl_trajectory_count": _require(
                    rl_measurement, "trajectory_count"
                ),
                "rl_atif_overall_retention": _require(
                    rl_atif, "overall_retention"
                ),
                "rl_otel_overall_retention": _require(
                    rl_otel, "overall_retention"
                ),
                "rl_atif_environment_reset_retention": _require(
                    rl_atif,
                    "capabilities",
                    "environment_reset_state",
                    "retention",
                ),
                "rl_otel_environment_reset_retention": _require(
                    rl_otel,
                    "capabilities",
                    "environment_reset_state",
                    "retention",
                ),
                "rl_atif_reward_retention": _require(
                    rl_atif, "capabilities", "rewards", "retention"
                ),
                "rl_otel_reward_retention": _require(
                    rl_otel, "capabilities", "rewards", "retention"
                ),
                "rl_atif_termination_retention": _require(
                    rl_atif, "capabilities", "termination", "retention"
                ),
                "rl_otel_termination_retention": _require(
                    rl_otel, "capabilities", "termination", "retention"
                ),
                "coding_atif_tool_call_retention": _require(
                    coding_atif, "capabilities", "tool_calls", "retention"
                ),
                "coding_otel_tool_call_retention": _require(
                    coding_otel, "capabilities", "tool_calls", "retention"
                ),
                "coding_otel_replay_identity_retention": _require(
                    coding_otel,
                    "capabilities",
                    "replay_identity",
                    "retention",
                ),
                "rl_known_missing_field_count": len(
                    _require(rl_family, "source_pin", "known_missing_fields")
                ),
                "rl_memory_snapshot_fields_missing": all(
                    field in _require(
                        rl_family, "source_pin", "known_missing_fields"
                    )
                    for field in (
                        "memory_snapshot_before",
                        "memory_snapshot_after",
                        "memory_source_lineage",
                        "prompt_after_memory_injection",
                    )
                ),
            },
            "blocking_gap": (
                "the pinned real collector path passed, but a wholly upstream-"
                "dropped trace requires an out-of-band source/export manifest; "
                "production storage/failover and ATIF's deliberate enterprise-"
                "event non-reversibility remain. The RL round trip is a separate "
                "loss receipt: coding tool structure is retained better than RL "
                "reset/reward/termination state, and the pinned RL source omits "
                "memory snapshots and authorization fields. Neither projection "
                "is a sufficient memory or skill-learning authority"
            ),
        },
        "L1_personal_authority": {
            "status": "local_partial_pass" if all_denied_zero else "fail",
            "evidence": {
                "private_trajectories": _require(
                    wisp, "authorized_counts", "trajectories"
                ),
                "all_tested_denials_zero_before_ranking": all_denied_zero,
                "history_page_p95_ms": latency["personal_history_page"][
                    "p95_ms"
                ],
                "proposal_queue_p95_ms": latency["proposal_queue"]["p95_ms"],
                "public_history_representations_audited": len(
                    _require(native_history, "datasets")
                ),
                "complete_public_harness_homes_found": len(
                    _require(
                        native_history,
                        "classification",
                        "complete_harness_home",
                    )
                ),
                "near_complete_public_harness_home_states_found": len(
                    _require(
                        history_discovery,
                        "classification",
                        "near_complete_home_state",
                    )
                ),
                "github_native_claude_files_in_top_repos": _require(
                    history_discovery,
                    "discovery_scale",
                    "top_repo_native_claude_files",
                ),
                "github_native_codex_files_in_top_repos": _require(
                    history_discovery,
                    "discovery_scale",
                    "top_repo_native_codex_files",
                ),
                "codex_repositories_with_auth_adjacent": _require(
                    history_discovery,
                    "security_observation",
                    "codex_repositories_with_auth_adjacent",
                ),
                "trace_commons_source_attested": trace_commons_attestation_passed,
                "trace_commons_sessions": trace_commons_s0.get("sessions"),
                "trace_commons_records": trace_commons_s0.get("valid_records"),
                "trace_commons_reproduction_passed": _require(
                    trace_commons_repro, "all_passed"
                ),
                "trace_commons_reproduction_metrics_compared": _require(
                    trace_commons_repro, "metrics_compared"
                ),
            },
            "blocking_gap": (
                "permission-oracle equality across every surface, deletion "
                "closure, concurrent policy churn, restart, replica, and "
                "failover remain untested"
            ),
        },
        "L2_cheap_evidence_finding": {
            "status": "does_not_meet_gate",
            "evidence": {
                "codetrace_test_rows": _require(
                    codetrace, "split_audit", "verified_counts", "test"
                ),
                "structural_precision": structural_arm["precision"],
                "random_precision_mean": random_arm["precision_mean"],
                "structural_precision_lift": (
                    structural_lift_over_random_mean
                ),
                "required_absolute_lift": 0.15,
                "exceeds_random_95_interval": (
                    structural_exceeds_random_interval
                ),
                "ties_trace_length": (
                    structural_arm["precision"]
                    == e1_arms["trace_length"]["precision"]
                ),
            },
            "decision": (
                "retain deterministic signals as review filters plus a random "
                "audit stratum; do not claim enrichment gate success"
            ),
        },
        "L3_diagnosis_and_eval_proposals": {
            "status": "mixed_partial",
            "diagnosis": {
                "best_blind_method": "reverse_chronology",
                "best_blind_top1": raw_e3_arms["I0T0J0"][
                    "top1_accuracy"
                ],
                "combined_top1": raw_e3_arms["I1T1J1"]["top1_accuracy"],
                "best_blind_top3": raw_e3_arms["I0T0J0"]["top3_accuracy"],
                "eligible_raw_traces": _require(
                    codetrace_raw, "e3_factorial", "eligible_traces"
                ),
                "pass": False,
                "reason": (
                    "the full deterministic factorial ran, but no evidence arm "
                    "beat reverse chronology and irrelevant errors changed "
                    "rankings; no calibrated judge or step-level causal verifier"
                ),
            },
            "retrospective_eval": {
                "combined_harmful_mutants": raw_e4_combined[
                    "harmful_mutants"
                ],
                "combined_kill_rate": raw_e4_combined[
                    "harmful_mutant_kill_rate"
                ],
                "allowed_variation_false_positive_rate": raw_e4_combined[
                    "allowed_variation_false_positive_rate"
                ],
                "pass": False,
                "reason": (
                    "high harmful-mutant sensitivity came with 48.6% benign "
                    "false positives; no changed-system rerun or step-level "
                    "causal verifier exists"
                ),
            },
                "multi_agent_taxonomy": {
                "released_judge_traces": _require(
                    mast, "llm_judge_annotations", "n"
                ),
                "finalized_human_judge_overlap": _require(
                    mast_overlap,
                    "exact_trace_sha256_overlap",
                    "finalized_human_vs_judge",
                ),
                "human_judge_scoring_status": mast_overlap[
                    "human_vs_judge_scoring_status"
                ],
                "pass": False,
                "reason": (
                    "released human and judge partitions cannot reproduce "
                    "finalized human-vs-judge accuracy"
                ),
                },
                "trace_commons_full_cohort": {
                    "source_attested": trace_commons_attestation_passed,
                    "aggregate_reproduction_passed": _require(
                        trace_commons_repro, "all_passed"
                    ),
                    "aggregate_reproduction_metrics_compared": _require(
                        trace_commons_repro, "metrics_compared"
                    ),
                    "structural_episode_candidates": trace_commons_s4.get(
                        "candidate_episodes"
                    ),
                    "eval_review_records": (
                        trace_commons_s6.get("candidate_records", {}).get(
                            "eval_review"
                        )
                    ),
                    "automatic_memory_or_skill_writes": (
                        trace_commons_s6.get("candidate_records", {}).get(
                            "automatic_memory_or_skill_writes"
                        )
                    ),
                },
            },
        "L4_semantic_candidate_retrieval": {
            "status": "offline_silver_and_local_rls_partial_pass",
            "evidence": {
                "documents": _require(e2_retrieval, "cohort", "documents"),
                "eligible_queries": _require(
                    e2_retrieval, "cohort", "eligible_queries"
                ),
                "best_offline_arm": "S1L0D1",
                "exact_recall_at_20": _require(
                    e2_retrieval,
                    "factorial",
                    "arms",
                    "S0L0D0",
                    "recall_at_20",
                ),
                "structured_dense_recall_at_20": _require(
                    e2_retrieval,
                    "factorial",
                    "arms",
                    "S1L0D1",
                    "recall_at_20",
                ),
                "recall_at_20_lift_over_exact": _require(
                    e2_retrieval,
                    "factorial",
                    "arms",
                    "S1L0D1",
                    "recall_at_20_delta_vs_exact",
                ),
                "recall_at_20_lift_95ci": _require(
                    e2_retrieval,
                    "factorial",
                    "arms",
                    "S1L0D1",
                    "recall_at_20_delta_95ci",
                ),
                "exact_identifier_no_regression": _require(
                    e2_retrieval,
                    "acceptance",
                    "exact_identifier_no_regression",
                ),
                "human_label_gate_passed": _require(
                    e2_retrieval,
                    "acceptance",
                    "human_label_gate_passed",
                ),
                "joint_local_postgres_gate_passed": _require(
                    e2_joint,
                    "acceptance",
                    "same_candidate_local_postgres_quality_and_rls_gate_passed",
                ),
                "all_denied_pre_ranking_candidates_zero": _require(
                    e2_joint,
                    "postgresql",
                    "all_denied_pre_ranking_candidates_zero",
                ),
                "lifecycle_oracles_passed": _require(
                    e2_joint, "postgresql", "lifecycle_oracles", "passed"
                ),
                "post_rollback_visible_rows": _require(
                    e2_joint,
                    "postgresql",
                    "rollback",
                    "post_rollback_visible_rows",
                ),
                "postgres_exact_pgvector_recall_at_20": _require(
                    e2_joint,
                    "postgresql",
                    "quality_against_silver_task_labels",
                    "postgres_exact_pgvector",
                    "recall_at_20",
                ),
                "postgres_hybrid_recall_at_20": _require(
                    e2_joint,
                    "postgresql",
                    "quality_against_silver_task_labels",
                    "postgres_hybrid_rrf",
                    "recall_at_20",
                ),
                "postgres_exact_pgvector_p50_ms": _require(
                    e2_joint,
                    "postgresql",
                    "client_observed_sequential_latency",
                    "postgres_exact_pgvector",
                    "p50_ms",
                ),
                "postgres_hybrid_p50_ms": _require(
                    e2_joint,
                    "postgresql",
                    "client_observed_sequential_latency",
                    "postgres_hybrid_rrf_end_to_end",
                    "p50_ms",
                ),
                "aurora_gate_passed": _require(
                    e2_joint, "acceptance", "real_aurora_gate_passed"
                ),
                "concurrency_or_scale_gate_passed": _require(
                    e2_joint,
                    "acceptance",
                    "concurrency_or_scale_gate_passed",
                ),
            },
            "decision": (
                "retain exact and structured retrieval and conditionally add "
                "the pinned general dense lane; reject the tested "
                "FTS/trigram/vector RRF because its tiny recall lift loses "
                "ranking quality and adds about two orders of magnitude local "
                "latency. Human labels, Aurora, concurrency, and scale remain "
                "open; no custom embedding or database replacement is authorized"
            ),
        },
        "L5_temporal_memory": {
            "status": "real_trace_transition_partial_pass",
            "evidence": {
                "wisp_fact_proposals": _require(
                    wisp, "authorized_counts", "fact_proposals"
                ),
                "bitemporal_assertions_passed": _require(
                    memory, "assertions", "passed"
                ),
                "bitemporal_assertions_total": _require(
                    memory, "assertions", "total"
                ),
                "bitemporal_assertions_failed": _require(
                    memory, "assertions", "failed"
                ),
                "real_trace_records": _require(
                    trace_memory, "native_trace_fidelity", "records"
                ),
                "real_resolved_parent_edges": _require(
                    trace_memory,
                    "native_trace_fidelity",
                    "resolved_parent_edges",
                ),
                "real_unresolved_parent_edges": _require(
                    trace_memory,
                    "native_trace_fidelity",
                    "unresolved_parent_edges",
                ),
                "real_context_artifact_calls": _require(
                    trace_memory,
                    "memory_lifecycle",
                    "context_artifact_calls",
                ),
                "real_joined_context_artifact_results": _require(
                    trace_memory,
                    "memory_lifecycle",
                    "joined_context_artifact_results",
                ),
                "real_exact_cross_session_continuities": _require(
                    trace_memory,
                    "memory_lifecycle",
                    "exact_write_to_later_read",
                ),
                "real_interval_censored_version_gaps": _require(
                    trace_memory,
                    "memory_lifecycle",
                    "interval_censored_version_gaps",
                ),
                "real_reconstructable_edits": _require(
                    trace_memory,
                    "memory_lifecycle",
                    "reconstructable_edits",
                ),
                "real_unreconstructable_edits": _require(
                    trace_memory,
                    "memory_lifecycle",
                    "unreconstructable_edits",
                ),
                "real_negative_controls_passed": _require(
                    trace_memory, "negative_controls", "all_passed"
                ),
                "real_raw_content_emitted": _require(
                    trace_memory, "raw_content_emitted"
                ),
                "real_research_trace_strata_discovered": len(
                    _require(
                        history_discovery,
                        "classification",
                        "real_research_trace_strata",
                    )
                ),
                "paired_trace_memory_strata_discovered": len(
                    _require(
                        history_discovery,
                        "classification",
                        "paired_trace_and_memory_strata",
                    )
                ),
                "natural_factorial_histories": _require(
                    natural_memory, "discovery", "histories"
                ),
                "natural_factorial_source_records": _require(
                    natural_memory, "discovery", "source_records"
                ),
                "natural_factorial_eligible_queries": _require(
                    natural_memory, "design", "eligible_queries"
                ),
                "natural_factorial_arm_count": _require(
                    natural_memory, "design", "arm_count"
                ),
                "natural_factorial_all_runnable_exact": _require(
                    natural_memory,
                    "composition_summary",
                    "all_runnable_mechanisms_exact",
                ),
                "natural_factorial_singleton_exact": _require(
                    natural_memory,
                    "composition_summary",
                    "strongest_singleton_exact",
                ),
                "natural_factorial_treatment_contrast_identifiable": _require(
                    natural_memory,
                    "treatment_contrast_gate",
                    "differential_mechanism_effect_identifiable",
                ),
                "natural_factorial_dream_gate": _require(
                    natural_memory,
                    "mechanism_gates",
                    "released_dream",
                    "status",
                ),
            },
            "decision": (
                "copy-on-write correction, authority intersection, rollback, "
                "deletion closure, influence exclusion, and stale-epoch denial "
                "pass in a deterministic oracle; one real public two-session "
                "cohort additionally proves one exact write/read continuity, "
                "two edit replays, and one correctly quarantined version gap. "
                "A fresh 217-history, 23-query, 16-arm natural memory factorial "
                "shows every runnable singleton and the composed arm at 16/23; "
                "the mechanisms are therefore observationally indistinguishable "
                "on current-state reads. PostgreSQL/RLS execution, memory quality, "
                "and memory utility remain unproven"
            ),
        },
        "L6_procedural_replay": {
            "status": "governed_release_mechanics_partial_pass",
            "evidence": {
                "wisp_recovery_review_candidates": _require(
                    recovery,
                    "corpora",
                    "wisp",
                    "constructor",
                    "matched_episodes",
                ),
                "share_codex_recovery_review_candidates": _require(
                    recovery,
                    "corpora",
                    "share_codex_sparse",
                    "constructor",
                    "matched_episodes",
                ),
                "agenttrace_rows": _require(agenttrace, "corpus", "rows"),
                "agenttrace_nl2bash_rows": _require(
                    agenttrace, "nl2bash_replay", "historical_rows"
                ),
                "bounded_pairs_executed": _require(
                    agenttrace, "nl2bash_replay", "executed_rows"
                ),
                "stdout_exit_equivalent_pairs": _require(
                    agenttrace, "nl2bash_replay", "equivalent_rows"
                ),
                "trace2skill_real_tool_boundary_passed": _require(
                    trace2skill_stage0,
                    "findings",
                    "sandbox_boundary_executed_real_model_tool_calls",
                ),
                "trace2skill_stage0_skill_benefit_established": _require(
                    trace2skill_stage0,
                    "findings",
                    "skill_benefit_established",
                ),
                "statebench_sql_fixture_tasks": _require(
                    statebench_sql, "runner", "total_tasks"
                ),
                "statebench_executable_gold_sql_tasks": _require(
                    statebench_sql, "runner", "gold_sql_tasks"
                ),
                "governed_release_assertions_passed": _require(
                    skill_release, "assertions", "passed"
                ),
                "governed_release_assertions_failed": _require(
                    skill_release, "assertions", "failed"
                ),
                "security_violation_veto_passed": _require(
                    skill_release,
                    "gates",
                    "any_security_violation_vetoes_release",
                ),
                "hidden_test_boundary_passed": _require(
                    skill_release,
                    "gates",
                    "hidden_test_invisible_to_proposer",
                ),
                "skill_meta_study_count": _require(
                    skill_optimization_meta, "study_count"
                ),
                "skill_meta_trace_mined_protocol_studies": _require(
                    skill_optimization_meta,
                    "strata",
                    "trace_mined_candidate",
                    "protocol_studies",
                ),
                "skill_meta_trace_mined_semantic_studies": _require(
                    skill_optimization_meta,
                    "strata",
                    "trace_mined_candidate",
                    "semantic_studies",
                ),
                "skill_meta_causal_benefit_confirmed": _require(
                    skill_optimization_meta,
                    "claim_boundary",
                    "causal_skill_benefit_confirmed",
                ),
                "skill_meta_automatic_promotion_authorized": _require(
                    skill_optimization_meta,
                    "claim_boundary",
                    "automatic_promotion_authorized",
                ),
                "skill_transfer_models": skill_transfer_models,
                "skill_transfer_harnesses": skill_transfer_harnesses,
                "skill_transfer_same_fixture_compared": _require(
                    skill_harness_transfer,
                    "claim_boundary",
                    "same_fixture_compared",
                ),
                "skill_cross_harness_same_fixture_compared": _require(
                    skill_cross_harness_transfer,
                    "claim_boundary",
                    "same_fixture_compared",
                ),
                "skill_qwen_native_model": _require(
                    skill_qwen_native, "request_model_id"
                ),
                "skill_qwen_native_harness": _require(
                    skill_qwen_native, "harness", "id"
                ),
                "skill_qwen_native_terminal_match_rates": {
                    name: _require(value, "expected_terminal_match_rate")
                    for name, value in qwen_native_variants.items()
                },
                "skill_qwen_native_native_tool_call_counts": {
                    name: _require(value, "native_tool_calls")
                    for name, value in qwen_native_variants.items()
                },
                "gepa_optimizer_executed": _require(
                    gepa_protocol, "claim_boundary", "optimizer_executed"
                ),
                "gepa_holdout_split_used": _require(
                    gepa_protocol, "claim_boundary", "holdout_split_used"
                ),
                "gepa_baseline_holdout_match_rate": _require(
                    gepa_protocol, "baseline", "holdout", "match_rate"
                ),
                "gepa_selected_holdout_match_rate": _require(
                    gepa_protocol, "selected", "holdout", "match_rate"
                ),
                "gepa_selected_candidate_characters": _require(
                    gepa_protocol, "selected", "candidate_characters"
                ),
                "gepa_metric_calls": _require(
                    gepa_protocol, "selected", "gepa_total_metric_calls"
                ),
                "gepa_enterprise_skill_benefit_confirmed": _require(
                    gepa_protocol,
                    "claim_boundary",
                    "enterprise_skill_benefit_confirmed",
                ),
                "matm_skill_retrieval_rows": _require(
                    matm_skill_retrieval, "dataset", "rows"
                ),
                "matm_skill_retrieval_model_folds": _require(
                    matm_skill_retrieval, "protocol", "held_out_models"
                ),
                "matm_successful_neighbor_top10_rate": _require(
                    matm_skill_retrieval,
                    "aggregate",
                    "successful_trace_neighbor",
                    "top_10_percent_success_rate",
                ),
                "matm_all_neighbor_top10_rate": _require(
                    matm_skill_retrieval,
                    "aggregate",
                    "all_trace_neighbor",
                    "top_10_percent_success_rate",
                ),
                "matm_successful_neighbor_top10_lift": _require(
                    matm_skill_retrieval,
                    "aggregate",
                    "contrast",
                    "successful_minus_all_top_10_percent_success_rate_mean",
                ),
                "matm_successful_neighbor_top10_lift_ci95": _require(
                    matm_skill_retrieval,
                    "aggregate",
                    "contrast",
                    "successful_minus_all_top_10_percent_success_rate_ci95",
                ),
                "matm_successful_neighbor_auc_lift": _require(
                    matm_skill_retrieval,
                    "aggregate",
                    "contrast",
                    "successful_minus_all_auc_mean",
                ),
                "matm_successful_neighbor_auc_lift_ci95": _require(
                    matm_skill_retrieval,
                    "aggregate",
                    "contrast",
                    "successful_minus_all_auc_ci95",
                ),
                "matm_offline_predictive_transfer_measured": _require(
                    matm_skill_retrieval,
                    "claim_boundary",
                    "offline_predictive_transfer_measured",
                ),
                "matm_causal_skill_benefit_confirmed": _require(
                    matm_skill_retrieval,
                    "claim_boundary",
                    "causal_skill_benefit_confirmed",
                ),
            },
            "decision": (
                "the real tool sandbox and governed proposal/evaluation/release "
                "state machine pass, but neither establishes causal skill "
                "benefit. AgentTrace lacks task verdicts and intervention arms; "
                "the finance SQL fixture has only four executable gold queries. "
                f"The paired skill meta-analysis covers {skill_optimization_meta['study_count']} endpoint strata across "
                "two live local models and two tool-loop harnesses, but its "
                "protocol and semantic endpoints remain heterogeneous and no "
                "promotion is authorized. GEPA v0.1.4 executed 11 metric calls "
                "on a train/holdout protocol split and retained the empty seed "
                "at 2/3 holdout matches, so the optimizer arm produced no lift. "
                f"The offline MATM leave-one-model-out arm gives a "
                f"{matm_skill_retrieval['aggregate']['contrast']['successful_minus_all_top_10_percent_success_rate_mean']:.3f} "
                "top-10 recommendation lift (95% CI -0.020 to 0.166) but a "
                f"{matm_skill_retrieval['aggregate']['contrast']['successful_minus_all_auc_mean']:.3f} "
                "mean AUC contrast (95% CI -0.112 to 0.002); this is predictive "
                "evidence only, not changed-agent skill benefit. Run the "
                "preregistered 60–120 task "
                "schema-family-held-out NL2SQL experiment before releasing any "
                "learned procedure"
            ),
        },
        "L7_to_L10": {
            "status": "gated",
            "evidence": {
                "cmu_requirement_waived": False,
                "cmu_raw_access_approved": False,
                "cmu_metrics_run": False,
                "public_corpora_sufficient_for_current_gates": False,
            },
            "decision": (
                "no utility routing, enterprise release, domain embedding "
                "adaptation, or generator fine-tuning claim is authorized; "
                "the pinned CMU raw shard remains approval-gated, and "
                "prospective labels and outcomes remain blocking evidence"
            ),
        },
    }

    enterprise_questions = {
        "show_each_user_all_currently_authorized_history": {
            "status": "local_mechanics_supported",
            "basis": (
                "Wisp governed PostgreSQL pagination/denial plus seven public "
                "native-or-derived history fidelity audits"
            ),
            "next_gate": "complete permission-oracle/deletion/failover gauntlet",
        },
        "find_repeated_friction_and_later_recovery": {
            "status": "review_candidates_supported",
            "basis": "one canonical constructor on Wisp and share-codex",
            "next_gate": "human outcome labels and prospective validation",
        },
        "suggest_evals_from_traces": {
            "status": "proposal_and_audit_mechanics_supported",
            "basis": (
                "Wisp evidence-linked proposals, CodeTraceBench mutation "
                "mechanics, and an 18-assertion governed hidden-test/release "
                "lifecycle"
            ),
            "next_gate": (
                "guided harness/environment/verifier construction and "
                "changed-system execution"
            ),
        },
        "write_memory_or_memory_md": {
            "status": "not_supported",
            "basis": (
                "real native transition import is loss-aware, but Wisp "
                "correctly emitted zero fact proposals and no intervention "
                "tested whether memory improved later work"
            ),
            "next_gate": (
                "bitemporal contradiction benchmark, citations, review, "
                "rollback, and later-query utility"
            ),
        },
        "find_people_doing_similar_work": {
            "status": "not_tested",
            "basis": (
                "the audited public histories have no stable user field and "
                "cannot be treated as an independent cross-user enterprise cohort"
            ),
            "next_gate": (
                "authorized SWE-chat or consented enterprise same-task labels "
                "with cohort privacy"
            ),
        },
        "identify_missing_cloud_or_domain_skills": {
            "status": "not_supported",
            "basis": (
                "CodeTrace/MAST labels describe trajectory events, not human "
                "capability"
            ),
            "next_gate": (
                "reviewed capability taxonomy, environmental-availability "
                "labels, abstention, and prospective task uplift"
            ),
        },
        "recommend_collaboration": {
            "status": "not_supported",
            "basis": "trace similarity is not collaboration utility",
            "next_gate": (
                "reciprocal opt-in introductions and independently measured "
                "outcomes under minimum cohorts"
            ),
        },
        "fine_tune_enterprise_embeddings": {
            "status": "premature",
            "basis": (
                "a general structured+dense arm already improved silver-label "
                "Recall@20 by 0.0859 while dense alone added only 0.0051; the "
                "remaining gates are human labels, exact-identifier protection, "
                "Aurora/selective-scope scale, and prospective utility"
            ),
            "next_gate": (
                "at least +5 absolute Recall@20 over the general hybrid "
                "baseline without RLS/deletion/latency regression"
            ),
        },
    }

    output = {
        "schema_version": SCHEMA_VERSION,
        "input_receipts": receipts,
        "levels": levels,
        "enterprise_questions": enterprise_questions,
        "architecture_decision": {
            "persistent_systems": [
                "one governed PostgreSQL canonical evidence and proposal store"
            ],
            "projections": [
                "ATIF v1.7 for explicitly mapped portable tasks/evals",
                "OpenInference/OTLP for content-minimized operational topology",
            ],
            "new_database_justified": False,
            "custom_embedding_model_justified": False,
            "reason": (
                "the real OTel path, relational memory oracle, real native "
                "memory-transition adapter, and same-candidate forced-RLS "
                "PostgreSQL retrieval plus governed skill-release lifecycle "
                "pass without a second authority; the full Trace Commons "
                "cohort adds attested proposal mechanics without outcome labels. "
                "Exact pgvector is fast on the correctness cohort while the "
                "tested trigram-heavy fusion is rejected; current failures are "
                "labels, scale, outcome validity, calibration, and prospective "
                "causality—not a demonstrated need for another database"
            ),
        },
        "overall_status": (
            "real OTel conformance, governed history mechanics, synthetic "
            "memory invariants, and one loss-aware real memory transition "
            "cohort pass; silver-label retrieval, same-candidate local "
            "PostgreSQL RLS, and governed skill-release mechanics pass "
            "partially; memory utility, diagnosis, causal skill benefit, "
            "cross-user learning, Aurora scale, and prospective enterprise "
            "utility do not"
        ),
    }
    output["result_sha256"] = hashlib.sha256(
        stable_json(output).encode("utf-8")
    ).hexdigest()
    return output


def render_markdown(matrix: dict[str, Any]) -> str:
    levels = matrix["levels"]
    questions = matrix["enterprise_questions"]
    lines = [
        "# Frankengate combined empirical evidence matrix",
        "",
        "**Run date:** 2026-08-02",
        "",
        "## Bottom line",
        "",
        matrix["overall_status"].capitalize() + ".",
        "",
        "The combined evidence supports a small governed product: personal history, "
        "content-minimized structural review queues, and evidence-linked eval/procedure "
        "proposals. It does not support root-cause automation, employee skill inference, "
        "automatic memory writes, collaborator matching, or embedding fine-tuning.",
        "",
        "## Program levels",
        "",
        "| Level | Status | Decisive interpretation |",
        "| --- | --- | --- |",
    ]
    interpretations = {
        "L0_evidence_conformance": (
            "real OTel round trip passes; RL reset/reward fields are lossy and whole-trace upstream loss still needs a source manifest"
        ),
        "L1_personal_authority": (
            "tested denials are zero before ranking; production authority closure remains"
        ),
        "L2_cheap_evidence_finding": (
            "structural selection ties length and misses the +15-point gate"
        ),
        "L3_diagnosis_and_eval_proposals": (
            "raw eval mutation is sensitive but brittle; diagnosis and multi-agent gold do not pass"
        ),
        "L4_semantic_candidate_retrieval": (
            "structured+dense wins the silver cohort; exact pgvector is the "
            "smallest local RLS lane and the tested trigram hybrid is rejected"
        ),
        "L5_temporal_memory": (
            "real transition import and synthetic temporal/authority invariants pass; "
            "the 217-history natural factorial finds no singleton/composed contrast; "
            "memory quality and utility do not"
        ),
        "L6_procedural_replay": (
            "safe tool execution and hidden-test release mechanics pass; causal "
            "skill benefit does not"
        ),
        "L7_to_L10": (
            "CMU raw access is approval-gated; prospective enterprise labels, "
            "privacy, and outcomes remain gated"
        ),
    }
    for name, value in levels.items():
        lines.append(
            f"| `{name}` | `{value['status']}` | {interpretations[name]} |"
        )

    l2 = levels["L2_cheap_evidence_finding"]["evidence"]
    l3 = levels["L3_diagnosis_and_eval_proposals"]
    l4 = levels["L4_semantic_candidate_retrieval"]["evidence"]
    memory = levels["L5_temporal_memory"]["evidence"]
    schema = levels["L0_evidence_conformance"]["evidence"]
    skill = levels["L6_procedural_replay"]["evidence"]
    lines.extend(
        [
            "",
            "## Cross-arm findings",
            "",
            f"- CodeTraceBench structural selection precision was "
            f"{l2['structural_precision']:.3f} versus random mean "
            f"{l2['random_precision_mean']:.3f}. The {l2['structural_precision_lift']:.3f} "
            "absolute lift is below the preregistered 0.15 gate, ties trace length, "
            "and does not exceed random's 95% interval.",
            f"- The best blind CodeTraceBench step-localization top-1 was "
            f"{l3['diagnosis']['best_blind_top1']:.3f}; the combined deterministic "
            f"arm reached {l3['diagnosis']['combined_top1']:.3f}. No evidence arm "
            "beat reverse chronology, so the result does not support deployable "
            "root-cause diagnosis.",
            f"- The combined retrospective assertion killed "
            f"{l3['retrospective_eval']['combined_harmful_mutants']} supported mutants "
            f"at {l3['retrospective_eval']['combined_kill_rate']:.3f} with "
            f"{l3['retrospective_eval']['allowed_variation_false_positive_rate']:.3f} "
            "allowed-event false positives. It remains annotation-derived and was not "
            "run against a changed agent.",
            f"- MAST has "
            f"{l3['multi_agent_taxonomy']['finalized_human_judge_overlap']} finalized "
            "human traces overlapping the judge release. Therefore released "
            "human-versus-judge accuracy cannot be reproduced; high Hamming accuracy "
            "from an always-negative classifier is class imbalance, not competence.",
            f"- Structured plus dense retrieval reached "
            f"{l4['structured_dense_recall_at_20']:.3f} Recall@20 versus "
            f"{l4['exact_recall_at_20']:.3f} for exact-only on silver task labels. "
            f"In the same-candidate forced-RLS PostgreSQL run, exact pgvector "
            f"reached {l4['postgres_exact_pgvector_recall_at_20']:.3f} at "
            f"{l4['postgres_exact_pgvector_p50_ms']:.3f} ms p50; the tested "
            f"three-way hybrid reached only {l4['postgres_hybrid_recall_at_20']:.3f} "
            f"at {l4['postgres_hybrid_p50_ms']:.3f} ms. Keep exact/structured plus "
            "conditional dense retrieval and reject that trigram-heavy hybrid.",
            f"- The governed skill lifecycle passed "
            f"{levels['L6_procedural_replay']['evidence']['governed_release_assertions_passed']} "
            "PostgreSQL assertions, including hidden-test isolation and a hard "
            "security-violation veto. The one-task Trace2Skill smoke established "
            "safe tool execution but no skill benefit; the local finance fixture "
            "has only four executable gold SQL tasks, so NL2SQL intervention "
            "quality remains untested.",
            f"- The ATIF/OTel RL crosswalk covers {schema['rl_trajectory_count']} "
            "MATM trajectories. ATIF retains only "
            f"{schema['rl_atif_overall_retention']:.3f} of measured facts and OTel "
            f"{schema['rl_otel_overall_retention']:.3f}; reset-state retention is "
            f"{schema['rl_otel_environment_reset_retention']}, reward retention is "
            f"{schema['rl_otel_reward_retention']}, and termination retention is "
            f"{schema['rl_otel_termination_retention']}. The source also omits "
            "memory snapshots and authorization fields, so schema round-trip "
            "fidelity cannot be treated as skill-learning evidence.",
            f"- The paired skill meta-analysis contains "
            f"{skill['skill_meta_study_count']} endpoint strata, including "
            f"{skill['skill_meta_trace_mined_protocol_studies']} protocol and "
            f"{skill['skill_meta_trace_mined_semantic_studies']} semantic "
            "trace-mined comparisons. The same fixture was exercised across "
            f"{', '.join(skill['skill_transfer_models'])} and "
            f"{', '.join(skill['skill_transfer_harnesses'])}; causal benefit and "
            "automatic promotion remain false.",
            f"- A fresh Qwen3 4B native-Ollama replay completed all 18 episodes "
            f"but produced native tool-call counts "
            f"{skill['skill_qwen_native_native_tool_call_counts']} and zero "
            "terminal matches in every arm. This is a typed harness/model null, "
            "not evidence that the trace-mined candidate improves or harms "
            "semantic task quality.",
            f"- GEPA v0.1.4 ran {skill['gepa_metric_calls']} metric calls with a "
            f"three-episode train split and three-episode holdout. The selected "
            f"candidate matched the empty seed at {skill['gepa_selected_holdout_match_rate']:.3f} "
            "on holdout, so this optimizer arm produced no protocol lift and "
            "does not support automatic skill promotion.",
            f"- The MATM outcome-conditioned successful-neighbor arm covered "
            f"{skill['matm_skill_retrieval_rows']} rows across "
            f"{skill['matm_skill_retrieval_model_folds']} held-out model folds. "
            f"Its top-10 recommendation rate was {skill['matm_successful_neighbor_top10_rate']:.3f} "
            f"versus {skill['matm_all_neighbor_top10_rate']:.3f} for all-trace neighbors "
            f"(lift {skill['matm_successful_neighbor_top10_lift']:.3f}), but mean AUC "
            f"fell by {abs(skill['matm_successful_neighbor_auc_lift']):.3f}; the "
            "bootstrap intervals cross zero, so this is promising recommendation "
            "signal rather than causal skill evidence.",
            f"- The natural memory factorial covers {memory['natural_factorial_histories']} histories "
            f"and {memory['natural_factorial_eligible_queries']} eligible reads across "
            f"{memory['natural_factorial_arm_count']} arms. Every runnable singleton "
            f"and the composed arm reached {memory['natural_factorial_singleton_exact']}/"
            f"{memory['natural_factorial_eligible_queries']} exact availability; the "
            "differential mechanism gate is not identifiable, and released Dream/procedure "
            "arms remain gated because no independently released natural artifacts exist.",
            "- The attested 28-session Trace Commons cohort produced "
            f"{l3['trace_commons_full_cohort']['structural_episode_candidates']} "
            "structural temporal candidates and "
            f"{l3['trace_commons_full_cohort']['eval_review_records']} "
            "eval-review records, while automatic memory/skill writes remained "
            "zero. The full analysis was rerun from the local pinned corpus and "
            f"matched {l3['trace_commons_full_cohort']['aggregate_reproduction_metrics_compared']} "
            "aggregate metrics. This expands proposal mechanics, not outcome or "
            "skill evidence.",
            "",
            "## Original enterprise questions",
            "",
            "| Question | Current answer | Required next evidence |",
            "| --- | --- | --- |",
        ]
    )
    labels = {
        "show_each_user_all_currently_authorized_history": "Show each user all history",
        "find_repeated_friction_and_later_recovery": "Repeated friction/recovery",
        "suggest_evals_from_traces": "Suggested evals",
        "write_memory_or_memory_md": "Memory / MEMORY.md",
        "find_people_doing_similar_work": "Similar work across users",
        "identify_missing_cloud_or_domain_skills": "Missing cloud/domain skills",
        "recommend_collaboration": "Who should collaborate",
        "fine_tune_enterprise_embeddings": "Enterprise embedding fine-tuning",
    }
    for name, value in questions.items():
        lines.append(
            f"| {labels[name]} | `{value['status']}` | {value['next_gate']} |"
        )
    lines.extend(
        [
            "",
            "## Architecture consequence",
            "",
            "Keep one governed PostgreSQL evidence/proposal authority. Export selected "
            "ATIF tasks and content-minimized OTel topology with loss receipts. Do not "
            "add a database or custom embedding model. Exact pgvector satisfies the "
            "current local correctness lane; the measured bottlenecks are human labels, "
            "Aurora/selective-scope scale, evidence validity, calibration, privacy, and "
            "prospective outcomes.",
            "",
            "Every input result is content-addressed in the aggregate JSON. No raw "
            "trace, identifier, prompt, tool argument/result, path, or authority value "
            "is emitted by this composition.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results, receipts = load_results(args.result_dir)
    matrix = build_matrix(results, receipts)
    markdown = render_markdown(matrix)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output_markdown.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
