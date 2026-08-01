#!/usr/bin/env python3
"""Audit which independently tested mechanisms may enter Frankengate.

This is intentionally conservative: protocol, retrieval, or infrastructure
success is not treated as downstream skill/memory utility. Every row names its
receipt and an explicit integration disposition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-integration-promotion-audit-v1"
RESULTS = Path(__file__).resolve().parent / "experiments/results"


MECHANISMS: tuple[dict[str, Any], ...] = (
    {
        "name": "skillgen_bird",
        "receipt": "skillgen-codex-bird-frontier-2026-08-02.json",
        "disposition": "quarantined_negative_utility",
        "reason": "held-out exact SQLite accuracy regressed 0.500 to 0.375; release gate rejected",
    },
    {
        "name": "rho_locomo",
        "receipt": "rho-frontier-locomo-bounded-2026-08-02.json",
        "disposition": "quarantined_negative_utility",
        "reason": "matched no-harness control beat the self-preference-accepted candidate by 0.192",
    },
    {
        "name": "rho_powered_candidate",
        "receipt": "rho-candidate-harness-powered-2026-08-02.json",
        "disposition": "quarantined_negative_bounded_utility",
        "reason": "rejected candidate trailed exact initial-harness control 0.643 to 0.388; five regressions, one win, two ties",
    },
    {
        "name": "reasoningbank_codex",
        "receipt": "reasoningbank-codex-frontier-bounded-2026-08-02.json",
        "disposition": "quarantined_negative_utility",
        "reason": "frozen held-out score trailed no-harness control by 0.110",
    },
    {
        "name": "skillopt_alfworld",
        "receipt": "alfworld-luna-skillopt-long-horizon-2026-08-02.json",
        "disposition": "quarantined_utility_unproven",
        "reason": "sufficient-horizon one-task replay had zero wins for no-skill, placebo, and SkillOpt",
    },
    {
        "name": "gepa",
        "receipt": "gepa-native-tool-protocol-2026-08-02-r2.json",
        "disposition": "quarantined_no_lift",
        "reason": "selected candidate matched the empty seed on holdout; no protocol lift",
    },
    {
        "name": "matm_embedding_retrieval",
        "receipt": "matm-embedding-similarity-benchmark-2026-08-02.json",
        "disposition": "shadow_review_only",
        "reason": "offline Recall@20 signal has no changed-agent utility or enterprise outcome label",
    },
    {
        "name": "governed_postgres_retrieval",
        "receipt": "finance-governed-retrieval-2026-08-02.json",
        "disposition": "shadow_backend_only",
        "reason": "RLS/deletion/retrieval mechanics pass locally; Aurora operations and downstream utility remain open",
    },
    {
        "name": "mlops_release_loop",
        "receipt": "mlops-feedback-canary-rollback-2026-08-02.json",
        "disposition": "mechanics_only",
        "reason": "canary and rollback state machine passes a deterministic fixture; no real candidate has passed utility",
    },
    {
        "name": "reasoningbank_azure_path",
        "receipt": "reasoningbank-locomo-bounded-2026-08-02.json",
        "disposition": "provider_unavailable",
        "reason": "documented Azure memory judge requires unavailable az executable",
    },
    {
        "name": "graphiti_langmem_natural",
        "receipt": "faithful-memory-components-llama32-natural-2026-08-02.json",
        "disposition": "incompatible_or_incomplete",
        "reason": "natural component run produced no completed Graphiti path and typed LangMem failures",
    },
    {
        "name": "agentrx_static",
        "receipt": "agentrx-independent-static-audit-2026-07-31.json",
        "disposition": "blocked_artifact",
        "reason": "bundled triggers and invariant snippets were not executable; diagnostic ablation covered only 3/10 failures",
    },
    {
        "name": "trace2skill_stage0",
        "receipt": "trace2skill-governed-stage0-2026-07-30.json",
        "disposition": "mechanics_only",
        "reason": "two-arm execution/verifier smoke test explicitly establishes mechanics, not skill utility or enterprise transfer",
    },
    {
        "name": "agentevals_stored_trace",
        "receipt": "agentevals-upstream-wisp-2026-07-30.json",
        "disposition": "stored_trace_assertion_only",
        "reason": "stored-trace assertions and mutation accounting ran, but no changed-system replay or downstream outcome was measured",
    },
    {
        "name": "signals_diagnosis_chain",
        "receipt": "signals-diagnosis-evals-test-checkpoint-2026-07-31.json",
        "disposition": "mechanics_only",
        "reason": "18/21 local chain tests passed with three skips; no blinded labels or prospective enterprise outcome was measured",
    },
    {
        "name": "dreaming_procedure",
        "receipt": "natural-model-dream-procedure-luna-meaningful-verification-2026-08-02.json",
        "disposition": "structural_only",
        "reason": "three of four meaningful structural projects verified; no changed-agent downstream utility outcome",
    },
    {
        "name": "memory_palace_meminsight_fixture",
        "receipt": "memory-mechanism-factorial-fixture-2026-07-30.json",
        "disposition": "fixture_only",
        "reason": "memory component factorial is a fixture/conformance arm and does not establish later-task utility",
    },
    {
        "name": "unselected_backend_concepts",
        "receipt": "concept-coverage-audit-2026-07-31.json",
        "disposition": "not_selected",
        "reason": "VectorChord, pg_textsearch, pgContext, TurboVec, and Turbopuffer are documented as not selected for the current architecture; no downstream utility promotion is implied",
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(result_dir: Path = RESULTS) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for mechanism in MECHANISMS:
        path = result_dir / mechanism["receipt"]
        if not path.exists():
            missing.append(mechanism["receipt"])
            continue
        receipt = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                **mechanism,
                "receipt_schema_version": receipt.get("schema_version"),
                "receipt_sha256": sha256(path),
            }
        )
    if missing:
        raise ValueError(f"missing promotion receipts: {sorted(missing)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "no_mechanism_eligible_for_automatic_integration",
        "rows": rows,
        "claim_boundary": {
            "automatic_integration_authorized": False,
            "independent_utility_gate_required": True,
            "reason": "No tested skill or memory mechanism has beaten a matched control on an adequately powered, independently graded held-out outcome. Backend and lifecycle mechanics remain shadow-only until downstream utility is measured.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, default=RESULTS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.result_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "rows": len(result["rows"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
