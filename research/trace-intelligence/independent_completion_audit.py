#!/usr/bin/env python3
"""Requirement-level audit for the independent-first research gate.

This audit is deliberately not a pass/fail efficacy score.  It makes the
remaining proof obligations explicit and refuses to infer completion from a
green protocol or infrastructure test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-independent-completion-audit-v1"


REQUIREMENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "complete_trace_admission",
        "status": "proven_for_admitted_public_slices",
        "evidence": (
            "independent-corpus-admission-2026-07-31.json",
            "corpus-admission-conformance-checkpoint-2026-07-31.json",
        ),
        "remaining": "Real enterprise traces with complete state/checkpoint/reward labels remain unadmitted or unavailable.",
    },
    {
        "id": "canonical_trace_loss_audit",
        "status": "proven_for_measured_formats",
        "evidence": ("canonical-projection-e0-conformance-2026-07-30.json",),
        "remaining": "Format-specific loss outside the measured fixtures still requires source-format coverage.",
    },
    {
        "id": "independent_upstream_reproduction",
        "status": "bounded_receipts_complete",
        "evidence": ("integration-promotion-audit-2026-08-02.json",),
        "remaining": "Some upstream paths are typed unavailable, structural-only, or fixture-only; no automatic promotion follows.",
    },
    {
        "id": "fair_controls_and_disjoint_splits",
        "status": "partial",
        "evidence": ("combined-evidence-matrix-2026-08-02.json",),
        "remaining": "Powered repeated-seed controls and broader task-family/user/time-disjoint cohorts remain open.",
    },
    {
        "id": "independent_outcome_evaluation",
        "status": "partial_mechanics_only",
        "evidence": (
            "enterprise-outcome-gate-conformance-2026-08-02.json",
            "enterprise-outcome-analysis-conformance-2026-08-02.json",
        ),
        "remaining": "Changed-agent future-task uplift, friction reduction, and cross-user transfer with human/adjudicated outcomes are unmeasured.",
    },
    {
        "id": "power_cost_latency_and_null_taxonomy",
        "status": "partial",
        "evidence": (
            "rho-candidate-harness-powered-2026-08-02.json",
            "mlops-feedback-canary-rollback-2026-08-02.json",
        ),
        "remaining": "The RHO powered slice has uncertainty but is not repeated-seed powered; cross-method cost/latency and calibrated null taxonomy remain incomplete.",
    },
    {
        "id": "separate_frankengate_integration",
        "status": "proven_none_authorized",
        "evidence": ("integration-promotion-audit-2026-08-02.json",),
        "remaining": "A separate integration experiment can begin only after an independent positive utility gate.",
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(result_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for requirement in REQUIREMENTS:
        evidence: list[dict[str, Any]] = []
        for filename in requirement["evidence"]:
            path = result_dir / filename
            if not path.exists():
                missing.append(filename)
                evidence.append({"path": filename, "exists": False})
            else:
                evidence.append({"path": filename, "exists": True, "sha256": sha256(path)})
        rows.append({**requirement, "evidence": evidence})
    if missing:
        raise ValueError(f"missing completion-audit evidence: {sorted(set(missing))}")
    promotion_path = result_dir / "integration-promotion-audit-2026-08-02.json"
    promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
    invalid_receipts: list[str] = []
    for row in promotion.get("rows", []):
        receipt_path = result_dir / row["receipt"]
        if not receipt_path.exists() or sha256(receipt_path) != row.get("receipt_sha256"):
            invalid_receipts.append(row.get("name", row.get("receipt", "unknown")))
    if invalid_receipts:
        raise ValueError(f"promotion receipt hash mismatch: {sorted(invalid_receipts)}")
    incomplete = [row for row in rows if row["status"] not in {"proven_for_admitted_public_slices", "proven_for_measured_formats", "bounded_receipts_complete", "proven_none_authorized"}]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "active_incomplete",
        "requirements": rows,
        "incomplete_requirement_ids": [row["id"] for row in incomplete],
        "receipt_integrity": {
            "promotion_rows": len(promotion.get("rows", [])),
            "all_embedded_hashes_verified": True,
        },
        "claim_boundary": {
            "objective_complete": False,
            "automatic_integration_authorized": False,
            "reason": "Protocol, storage, and lifecycle evidence does not prove causal skill, memory, retrieval, or enterprise outcome utility.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.result_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "incomplete": result["incomplete_requirement_ids"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
