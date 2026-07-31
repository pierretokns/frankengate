#!/usr/bin/env python3
"""Run the content-free enterprise outcome gate conformance receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import enterprise_outcome_gate as gate


def _decision(value: gate.GateDecision) -> dict[str, Any]:
    return {
        "decision": value.decision,
        "reason": value.reason,
        "candidate_count": value.candidate_count,
        "distinct_subject_count": value.distinct_subject_count,
        "labeled_candidate_count": value.labeled_candidate_count,
        "candidate_digest_count": len(value.candidate_digests),
    }


def build_result() -> dict[str, Any]:
    decisions = {
        name: _decision(value)
        for name, value in gate.conformance_cases().items()
    }
    checks = {
        "missing_consent_abstains_without_counts": (
            decisions["missing_consent"]["decision"] == "abstain"
            and decisions["missing_consent"]["candidate_count"] == 0
        ),
        "wrong_scope_abstains_without_counts": (
            decisions["wrong_consent_scope"]["decision"] == "abstain"
            and decisions["wrong_consent_scope"]["candidate_count"] == 0
        ),
        "missing_outcome_labels_abstains_without_counts": (
            decisions["cohort_without_labels"]["decision"] == "abstain"
            and decisions["cohort_without_labels"]["candidate_count"] == 0
        ),
        "authorized_cohort_has_minimum_subjects_and_labels": (
            decisions["authorized_labeled_cohort"]["decision"] == "allow"
            and decisions["authorized_labeled_cohort"]["distinct_subject_count"]
            >= 3
            and decisions["authorized_labeled_cohort"]["labeled_candidate_count"]
            == decisions["authorized_labeled_cohort"]["candidate_count"]
        ),
        "denials_emit_no_candidate_digests": all(
            value["candidate_digest_count"] == 0
            for name, value in decisions.items()
            if name != "authorized_labeled_cohort"
        ),
    }
    result = {
        "schema_version": "frankengate-enterprise-outcome-gate-conformance-v1",
        "gate_schema_version": gate.SCHEMA_VERSION,
        "decisions": decisions,
        "checks": checks,
        "all_passed": all(checks.values()),
        "claim_boundary": {
            "rls_and_scope_gate_mechanics_proven": all(checks.values()),
            "cross_user_similarity_quality_measured": False,
            "skill_gap_or_collaboration_utility_measured": False,
            "causal_enterprise_outcome_confirmed": False,
            "raw_trace_content_committed": False,
        },
        "required_inputs_before_enterprise_analysis": [
            "current authorization epoch",
            "tenant/team/classification/purpose scope",
            "explicit cross-user consent and matching row scope",
            "minimum three-subject cohort",
            "reviewed human outcome labels for outcome-bearing questions",
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = build_result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"all_passed": value["all_passed"]}, sort_keys=True))
    return 0 if value["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
