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


SCHEMA_VERSION = "frankengate-combined-evidence-matrix-v1"
REQUIRED_RESULTS = {
    "projection": "canonical-projection-e0-conformance-2026-07-30.json",
    "codetracebench": "codetracebench-manifest-e1-e3-e4-2026-07-30.json",
    "mast": "mast_multiagent_empirical-2026-07-30.json",
    "wisp_governed": "wisp-governed-postgres-benchmark-2026-07-30.json",
    "wisp_recovery": "wisp-share-codex-canonical-bounded-recovery-2026-07-30.json",
    "cmu_access": "cmu-access-audit-2026-07-30.json",
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
    codetrace = results["codetracebench"]
    mast = results["mast"]
    wisp = results["wisp_governed"]
    recovery = results["wisp_recovery"]
    cmu = results["cmu_access"]

    atif = _require(projection, "ATIF_v1_7")
    otel = _require(projection, "OpenInference_OTel")
    e1_arms = _require(codetrace, "e1_signal_selection", "arms")
    random_arm = _require(e1_arms, "uniform_random")
    structural_arm = _require(e1_arms, "structural_signal")
    e3_methods = _require(codetrace, "e3_decisive_step_diagnosis", "methods")
    e4_combined = _require(
        codetrace,
        "e4_eval_assertion_mutation",
        "aggregate_by_assertion",
        "combined",
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
    diagnosis_gain_over_random = (
        float(e3_methods["reverse_chronology"]["top1_accuracy"])
        - float(e3_methods["uniform_random"]["top1_accuracy"])
    )
    all_denied_zero = all(
        all(int(value) == 0 for value in counts.values())
        for counts in authority_matrix.values()
    )

    levels = {
        "L0_evidence_conformance": {
            "status": "partial",
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
            },
            "blocking_gap": (
                "no real collector round trip, incomplete native-source set, "
                "and ATIF is deliberately non-reversible for enterprise events"
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
                "best_blind_top1": e3_methods["reverse_chronology"][
                    "top1_accuracy"
                ],
                "random_top1": e3_methods["uniform_random"]["top1_accuracy"],
                "gain_over_random": diagnosis_gain_over_random,
                "annotation_oracle_top1": e3_methods[
                    "critical_stage_start_oracle"
                ]["top1_accuracy"],
                "pass": False,
                "reason": (
                    "no invariants×topology×judge factorial, deterministic "
                    "error baseline, calibrated abstention, or evidence entailment"
                ),
            },
            "retrospective_eval": {
                "combined_harmful_mutants": e4_combined[
                    "harmful_mutants"
                ],
                "combined_kill_rate": e4_combined[
                    "harmful_mutant_kill_rate"
                ],
                "allowed_variation_false_positive_rate": e4_combined[
                    "allowed_variation_false_positive_rate"
                ],
                "pass": False,
                "reason": (
                    "annotation-derived mutation mechanics passed, but no "
                    "independent verifier or changed-system rerun exists"
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
        },
        "L4_semantic_candidate_retrieval": {
            "status": "missing",
            "decision": (
                "do not add or fine-tune an embedding model until a common "
                "labelled candidate-set comparison beats exact+FTS+structured"
            ),
        },
        "L5_temporal_memory": {
            "status": "abstained",
            "evidence": {
                "wisp_fact_proposals": _require(
                    wisp, "authorized_counts", "fact_proposals"
                )
            },
            "decision": (
                "zero facts is the correct current output; temporal truth, "
                "contradiction, citation, and rollback tests are missing"
            ),
        },
        "L6_procedural_replay": {
            "status": "missing",
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
            },
            "decision": (
                "structural recovery candidates may seed reviewed procedures, "
                "but no no-memory/relevant/placebo/oracle replay has run"
            ),
        },
        "L7_to_L10": {
            "status": "gated",
            "evidence": {
                "cmu_access_status": _require(cmu, "result", "status"),
                "cmu_empirical_metrics_run": _require(
                    cmu, "result", "empirical_metrics_run"
                ),
            },
            "decision": (
                "no utility routing, enterprise release, domain embedding "
                "adaptation, or generator fine-tuning claim is authorized"
            ),
        },
    }

    enterprise_questions = {
        "show_each_user_all_currently_authorized_history": {
            "status": "local_mechanics_supported",
            "basis": "Wisp governed PostgreSQL pagination and denial matrix",
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
                "Wisp evidence-linked proposals plus CodeTraceBench mutation "
                "mechanics"
            ),
            "next_gate": (
                "guided harness/environment/verifier construction and "
                "changed-system execution"
            ),
        },
        "write_memory_or_memory_md": {
            "status": "not_supported",
            "basis": "Wisp correctly emitted zero fact proposals",
            "next_gate": (
                "bitemporal contradiction benchmark, citations, review, "
                "rollback, and later-query utility"
            ),
        },
        "find_people_doing_similar_work": {
            "status": "not_tested",
            "basis": "no admitted cross-user semantic/outcome cohort was run",
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
            "basis": "no frozen E2 hard slice or hybrid baseline comparison",
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
                "current failures are labels, outcome validity, calibration, "
                "and prospective causality—not demonstrated vector scale"
            ),
        },
        "overall_status": (
            "useful L0-L3 mechanics and negative results; no E0-E7 acceptance "
            "block is complete"
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
        "**Run date:** 2026-07-30",
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
            "OTel sidecar topology survives; ATIF enterprise-event identity does not"
        ),
        "L1_personal_authority": (
            "tested denials are zero before ranking; production authority closure remains"
        ),
        "L2_cheap_evidence_finding": (
            "structural selection ties length and misses the +15-point gate"
        ),
        "L3_diagnosis_and_eval_proposals": (
            "eval mutation mechanics work; diagnosis and multi-agent gold do not pass"
        ),
        "L4_semantic_candidate_retrieval": "no common labelled retrieval factorial",
        "L5_temporal_memory": "zero fact proposals is the correct abstention",
        "L6_procedural_replay": "recovery candidates exist; causal replay does not",
        "L7_to_L10": "prospective enterprise outcomes and CMU access remain gated",
    }
    for name, value in levels.items():
        lines.append(
            f"| `{name}` | `{value['status']}` | {interpretations[name]} |"
        )

    l2 = levels["L2_cheap_evidence_finding"]["evidence"]
    l3 = levels["L3_diagnosis_and_eval_proposals"]
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
            f"{l3['diagnosis']['best_blind_top1']:.3f}; the annotation-consuming "
            f"stage oracle reached {l3['diagnosis']['annotation_oracle_top1']:.3f}. "
            "Stages help navigation but do not supply deployable diagnosis.",
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
            "add a database or custom embedding model: the measured bottlenecks are "
            "evidence validity, labels, calibration, privacy, and prospective outcomes.",
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
