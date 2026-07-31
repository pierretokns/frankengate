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
                "experiments/summaries/atif-rl-roundtrip-2026-07-30.md",
            ),
            "decision": levels.get("L0_evidence_conformance", {}).get("status"),
            "open_gate": "ATIF/OTel projections lose load-bearing RL reset, reward, termination, memory, and authorization facts; canonical DAG remains required.",
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
                "experiments/results/natural-released-procedure-2026-08-02.json",
                "experiments/results/natural-released-procedure-verification-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-verification-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-llama-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-llama-verification-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-luna-2026-08-02.json",
                "experiments/results/natural-model-dream-procedure-luna-verification-2026-08-02.json",
                "experiments/results/alfworld-luna-skillopt-family4-2026-08-02.json",
                "experiments/results/alfworld-luna-skillopt-family4-verification-2026-08-02.json",
                "experiments/results/alfworld-luna-skillopt-long-horizon-2026-08-02.json",
                "experiments/results/alfworld-luna-skillopt-long-horizon-verification-2026-08-02.json",
                "experiments/summaries/skill-learning-faithful-preflight-2026-07-30.md",
                "experiments/summaries/skill-improvement-strategy-audit-2026-07-30.md",
                "experiments/summaries/natural-trace-memory-factorial-2026-08-02-r2.md",
            ),
            "open_gate": "Natural release lineage is exercised; Qwen3 4B passed zero of three structural proposal gates, while Llama 3.2 and frontier Luna each passed one of three. The frontier Luna SkillOpt checkpoint also produced zero wins for no-skill, placebo, and candidate across four previously unused ALFWorld families at a 12-step horizon, and a fair-horizon one-task follow-up remained zero-win at 35 steps; independent replay verification passed both. These results establish protocol/grounding mechanics only; semantic task utility and enterprise-labeled concept transfer remain unmeasured.",
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
            ),
            "decision": levels.get("L4_semantic_candidate_retrieval", {}).get("status"),
            "open_gate": "Managed Aurora semantics, extension compatibility, concurrency, and production SLOs are not measured; local PostgreSQL promotion, RLS, and WAL/PITR mechanics are measured separately.",
        },
        {
            "id": "cmu_and_enterprise_outcomes",
            "requirement": "Run public/CMU trace analyses and answer cross-user similarity, skill gaps, collaboration, and enterprise outcome questions.",
            "status": "cmu_approval_gated; enterprise_outcomes_unmeasured",
            "evidence": file_evidence(
                "experiments/summaries/cmu-access-and-adapter-readiness-2026-07-30.md",
                "experiments/results/combined-evidence-matrix-2026-08-02.json",
            ),
            "open_gate": "CMU publisher approval, stable user/consent labels, prospective human outcomes, and cross-user utility are still required.",
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
            ],
            "open_gate": "The overall program remains active until the research gates above close; publication mechanics themselves are functioning.",
        },
    ]
    return {
        "schema_version": "frankengate-program-scope-audit-v1",
        "overall_status": "active_incomplete",
        "matrix_schema_version": matrix.get("schema_version"),
        "program_audit_schema_version": program.get("schema_version"),
        "requirements": requirements,
        "open_requirements": program.get("requirements_still_open", []),
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
