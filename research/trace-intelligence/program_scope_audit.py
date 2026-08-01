#!/usr/bin/env python3
"""Machine-check the full Frankengate trace-intelligence research scope.

This is a completion ledger, not a success claim.  It records the strongest
current evidence for each objective and preserves open gates explicitly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "experiments/results"
SUMMARIES = ROOT / "experiments/summaries"
MATRIX_PATH = RESULTS / "combined-evidence-matrix-2026-08-02.json"
AUDIT_PATH = RESULTS / "program-completion-audit-2026-08-02.json"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def file_evidence(*paths: str) -> list[dict[str, Any]]:
    evidence = []
    for relative in paths:
        path = ROOT / relative
        evidence.append({"path": relative, "exists": path.exists()})
    return evidence


def git_value(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT.parent.parent, check=True,
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def build_audit() -> dict[str, Any]:
    matrix = load(MATRIX_PATH)
    program = load(AUDIT_PATH)
    levels = matrix.get("levels", {})
    requirements = [
        {
            "id": "schema_crosswalk",
            "requirement": "Compare ATIF, OpenInference/OTel, coding traces, and RL-environment traces.",
            "status": "partial_proven",
            "evidence": file_evidence(
                "experiments/results/canonical-projection-e0-conformance-2026-07-30.json",
                "experiments/results/atif-rl-roundtrip-2026-07-30.json",
                "experiments/results/atif-capability-extension-2026-08-02.json",
                "experiments/results/atif-capability-extension-luna-review-2026-08-02.json",
                "experiments/summaries/atif-rl-roundtrip-2026-07-30.md",
                "experiments/summaries/atif-capability-extension-2026-08-02.md",
            ),
            "decision": levels.get("L0_evidence_conformance", {}).get("status"),
            "open_gate": "Portable ATIF/OTel still lose load-bearing RL reset, reward, termination, memory, and authorization facts. The namespaced capability profile now preserves structural authority/epoch, reset/termination, reward, replay-reference, and memory-lineage facts for profile-aware readers (Wisp and MATM round trips completed); raw payload/state remains intentionally omitted and the canonical DAG remains required.",
        },
        {
            "id": "public_trace_and_concept_audit",
            "requirement": "Audit public Hugging Face traces and Dreams, Memory Palace, Hermes, Jeopard, SkillOpt, ReasoningBank, and RL concepts.",
            "status": "natural_release_mechanics_proven_utility_unproven",
            "evidence": file_evidence(
                "experiments/results/public-agent-history-discovery-2026-07-30.json",
                "experiments/results/skillopt-alfworld-intervention-readiness-2026-08-02.json",
                "experiments/results/skillopt-alfworld-local-runtime-attempt-r15-2026-08-02.json",
                "experiments/results/skillopt-alfworld-local-intervention-r16-2026-08-02.json",
                "experiments/results/skillopt-deterministic-lifecycle-r17-2026-08-02.json",
                "experiments/results/skillopt-alfworld-codex-r18-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r19-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r19-verification-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r20-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r20-verification-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r21-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r21-verification-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r22-real-candidate-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r22-real-candidate-verification-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r23-real-candidate-2026-08-02.json",
                "experiments/results/alfworld-codex-skillopt-r23-real-candidate-verification-2026-08-02.json",
                "experiments/results/skillopt-candidate-provenance-audit-2026-08-02.json",
                "experiments/results/matm-embedding-similarity-benchmark-2026-08-02.json",
                "experiments/results/rho-upstream-hermetic-audit-2026-08-01.json",
                "experiments/results/agentrx-independent-static-audit-2026-07-31.json",
                "experiments/results/skillgen-upstream-mechanics-audit-2026-08-01.json",
                "experiments/results/skillgen-codex-frontier-mini-2026-08-02.json",
                "experiments/results/skillgen-codex-bird-frontier-2026-08-02.json",
                "experiments/results/rho-frontier-locomo-bounded-2026-08-02.json",
                "experiments/results/rho-candidate-harness-powered-2026-08-02.json",
                "experiments/results/rho-initial-harness-repeat-powered-2026-08-02.json",
                "experiments/results/reasoningbank-locomo-bounded-2026-08-02.json",
                "experiments/results/reasoningbank-codex-frontier-bounded-2026-08-02.json",
                "experiments/results/alfworld-codex-four-family-35step-interrupted-2026-08-02.json",
                "experiments/results/skilllearnbench-frontier-subset-2026-08-01.json",
                "experiments/results/skilllearnbench-frontier-family-2026-08-05.json",
                "experiments/results/natural-released-procedure-2026-08-02.json",
                "experiments/results/natural-released-procedure-verification-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-verification-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-llama-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-llama-verification-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-luna-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-luna-verification-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-luna-meaningful-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-luna-meaningful-verification-2026-08-02.json",
                "experiments/results/alfworld-luna-skillopt-family4-2026-08-02.json",
                "experiments/results/alfworld-luna-skillopt-family4-verification-2026-08-02.json",
                "experiments/results/alfworld-luna-skillopt-long-horizon-2026-08-02.json",
                "experiments/results/alfworld-luna-skillopt-long-horizon-verification-2026-08-02.json",
                "experiments/summaries/skill-learning-faithful-preflight-2026-07-30.md",
                "experiments/summaries/skill-improvement-strategy-audit-2026-07-30.md",
                "experiments/summaries/natural-trace-memory-factorial-2026-08-02-r2.md",
                "experiments/summaries/skilllearnbench-frontier-subset-2026-08-01.md",
                "experiments/summaries/skilllearnbench-frontier-family-2026-08-05.md",
            ),
            "open_gate": "Natural release lineage is exercised; the corrected meaningful-trace Luna sample passed 3/4 structural proposal gates after excluding empty/malformed fixtures, while the earlier mixed sample passed 1/3. RHO targeted mechanics passed 29/29 while its full hermetic suite has typed failures; the powered rejected RHO candidate was independently replayed against the exact initial-harness control on eight held-out LOCOMO tasks and fell from 0.643 to 0.388 (delta -0.255, five regressions, one win, two ties; bootstrap interval crosses zero), so self-preference is not treated as utility. A separate matched initial-harness repeat scored 0.313 versus 0.643, exposing control variance that must be powered before a general claim. The pinned ReasoningBank LOCOMO attempt stopped before extraction because its documented Azure provider requires unavailable `az`, so it is provider-unavailable rather than a quality result. A Codex-adapted ReasoningBank run reached memory extraction and frozen held-out replay, but scored 0.593 versus the matched no-harness 0.703 (delta -0.110, one regression), so it is also quarantined. AgentRx static artifacts have trigger/compile defects; SkillGen compile/import, persistence, routing, and paired accounting mechanics pass. The Codex-frontier SkillGen all-pass cohort produced no candidate, while the executable BIRD-SQL cohort generated a candidate from 6/8 failures but lost held-out accuracy from 0.500 to 0.375 (zero repairs, one regression, net -1), so the release gate rejected it. Both runs used explicit provider/embedding substitutions. The MATM action-only embedding arm improved same-work Recall@20 over a lexical action baseline, but successful-neighbor precision confidence crosses zero and the label cohort is only 33 folds/636 queries. The frontier Luna SkillOpt checkpoint also produced zero wins for no-skill, placebo, and candidate across four previously unused ALFWorld families at a 12-step horizon, and a fair-horizon one-task follow-up remained zero-win at 35 steps; independent replay verification passed both. A further 35-step four-family Codex attempt was interrupted and explicitly unscored. These results establish protocol/grounding/retrieval mechanics and negative real-corpus efficacy slices; semantic enterprise transfer remains unmeasured.",
        },
        {
            "id": "single_and_composed_mechanisms",
            "requirement": "Test single and combined skill/memory mechanisms against held-out traces and RL environments.",
            "status": "family_disjoint_intervention_and_composition_proven; utility_unproven",
            "evidence": file_evidence(
                "experiments/results/memory-mechanism-factorial-fixture-2026-07-30.json",
                "experiments/results/alfworld-trace-skill-intervention-r3-2026-08-02.json",
                "experiments/results/alfworld-trace-skill-memory-composition-r6-2026-08-02.json",
                "experiments/results/alfworld-durable-memory-intervention-r7-2026-08-02.json",
                "experiments/results/alfworld-model-generated-memory-intervention-r8-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r9-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r9-verification-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r11-openai-llama-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r11-openai-llama-verification-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r12-replayable-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r12-semantic-verification-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r10-qwen-incomplete-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r13-controls-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r13-controls-verification-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r14-qwen-controls-2026-08-02.json",
                "experiments/results/alfworld-family-disjoint-powered-r14-qwen-controls-verification-2026-08-02.json",
            ),
            "open_gate": "No mechanism has a powered causal lift with independent later-task labels; all learned candidates remain rejected or proposal-only.",
        },
        {
            "id": "governed_local_stack",
            "requirement": "Exercise a local Aurora-like governed stack with PostgreSQL, RLS, vectors, deletion, and tool/eval release controls.",
            "status": "local_replication_rls_failover_proven; aurora_operations_unproven",
            "evidence": file_evidence(
                "experiments/results/wisp-governed-postgres-benchmark-2026-07-30.json",
                "experiments/results/wisp-share-codex-canonical-bounded-recovery-2026-07-30.json",
                "experiments/results/codetracebench-e2-postgres-joint-retrieval-2026-07-30.json",
                "experiments/results/bitemporal-memory-conformance-2026-07-30.json",
                "experiments/results/aurora-runtime-probe-2026-08-02.json",
                "experiments/results/aurora-like-replication-lab-2026-08-02.json",
                "experiments/results/postgres-pitr-lab-2026-08-02.json",
                "experiments/results/h5-concurrency-live-rerun-2026-08-02.json",
                "experiments/results/h5-concurrency-guarded-rerun-2026-08-02.json",
                "experiments/results/enterprise-outcome-gate-conformance-2026-08-02.json",
                "experiments/results/enterprise-outcome-analysis-conformance-2026-08-02.json",
                "experiments/results/mlops-feedback-canary-rollback-2026-08-02.json",
                "experiments/results/integration-promotion-audit-2026-08-02.json",
                "experiments/results/independent-completion-audit-2026-08-02.json",
            ),
            "decision": levels.get("L4_semantic_candidate_retrieval", {}).get("status"),
            "open_gate": "Managed Aurora semantics, extension compatibility, concurrency, and production SLOs are not measured; local PostgreSQL promotion, RLS, and WAL/PITR mechanics are measured separately. The deterministic MLOps canary/rollback lifecycle now passes mechanics, while real candidates remain quarantined because no causal utility lift has been demonstrated.",
        },
        {
            "id": "cmu_and_enterprise_outcomes",
            "requirement": "Run public/CMU trace analyses and answer cross-user similarity, skill gaps, collaboration, and enterprise outcome questions.",
            "status": "cmu_approval_gated; enterprise_outcomes_unmeasured",
            "evidence": file_evidence(
                "experiments/summaries/cmu-access-and-adapter-readiness-2026-07-30.md",
                "experiments/results/combined-evidence-matrix-2026-08-02.json",
                "experiments/results/enterprise-outcome-gate-conformance-2026-08-02.json",
                "experiments/results/enterprise-outcome-analysis-conformance-2026-08-02.json",
            ),
            "open_gate": "The fail-closed consent/epoch/classification/minimum-cohort gate and four answer-shaped content-free analyses now pass mechanics, but CMU publisher approval, stable user/consent labels, prospective human outcomes, and cross-user utility are still required.",
        },
        {
            "id": "publication_and_tracking",
            "requirement": "Publish reproducible artifacts on a dedicated branch and track work in GitHub issues and beads.",
            "status": "proven_for_current_checkpoint",
            "evidence": [
                {"branch": git_value("branch", "--show-current")},
                {"head": git_value("rev-parse", "HEAD")},
                {"remote": git_value("remote", "get-url", "origin")},
                {"github_issue": "https://github.com/pierretokns/frankengate/issues/93"},
                {"bead": "bif-kyy.17.13.4.4.5.3.2"},
                {"follow_on_beads": [
                    "bif-kyy.17.13.4.4.5.3.2.1",
                    "bif-kyy.17.13.4.4.5.3.2.2",
                    "bif-kyy.17.13.4.4.5.3.2.3",
                ]},
            ],
            "open_gate": "The overall program remains active until the research gates above close; publication mechanics themselves are functioning.",
        },
    ]
    # Keep the unresolved program gates explicit even when the upstream
    # combined-evidence matrix has no legacy ``requirements_still_open``
    # field.  An empty list here would contradict ``active_incomplete`` and
    # make a machine-readable audit appear complete by accident.
    open_requirements = [
        "CMU publisher approval and trajectory metrics",
        "positive causal skill utility and release-gated optimizer arms beyond completed controls",
        "semantic Dream/procedure utility and changed-system outcome evaluation",
        "prospective enterprise task outcomes and human labels",
        "managed Aurora semantics, extension compatibility, concurrency, and scale behavior",
        "consented minimum-cohort human outcome labels for cross-user analysis",
        "cross-user collaboration utility and consent outcomes",
        "matched SkillLearnBench and Recovery-Bench intervention outcomes",
    ]
    return {
        "schema_version": "frankengate-program-scope-audit-v1",
        "overall_status": "active_incomplete",
        "matrix_schema_version": matrix.get("schema_version"),
        "program_audit_schema_version": program.get("schema_version"),
        "requirements": requirements,
        "open_requirements": open_requirements,
        "claim_boundary": {
            "completion_confirmed": False,
            "causal_enterprise_utility_confirmed": False,
            "automatic_skill_or_memory_promotion_authorized": False,
            "raw_trace_content_committed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    result = build_audit()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Frankengate trace-intelligence program scope audit", "", "Overall status: **active incomplete**.", ""]
    for item in result["requirements"]:
        lines.append(f"## `{item['id']}` — {item['status']}")
        lines.append("")
        lines.append(item["requirement"])
        lines.append("")
        lines.append(f"Open gate: {item['open_gate']}")
        lines.append("")
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "requirements": len(result["requirements"]), "overall_status": result["overall_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
