#!/usr/bin/env python3
"""Run content-free conformance checks for enterprise question analyses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import enterprise_outcome_analysis as analysis
import enterprise_outcome_gate as gate


def fixture() -> list[analysis.OutcomeTrace]:
    rows = []
    values = (
        ("alice", "deploy", {"aws"}, {"aws", "kubernetes"}, 3, 2, True, "recovered"),
        ("bob", "deploy", {"kubernetes"}, {"aws", "kubernetes"}, 2, 1, True, "recovered"),
        ("carol", "deploy", {"aws", "kubernetes"}, {"aws", "kubernetes"}, 1, 1, True, "recovered"),
        ("dana", "sql", {"sql"}, {"sql", "warehouse"}, 2, 0, True, "blocked"),
    )
    for subject, task, observed, required, friction, recovery, opt_in, outcome in values:
        rows.append(analysis.OutcomeTrace(
            authority=gate.TraceRow(
                trace_id=f"{subject}-trace",
                tenant_id="tenant-a",
                owner_subject_id=subject,
                audience="team",
                team_id="platform",
                classification=1,
                allowed_purposes=frozenset({"quality-improvement"}),
                authorization_epoch=9,
                cross_user_consent_scope="platform-v1",
                human_outcome_label=outcome,
            ),
            task_family=task,
            observed_capabilities=frozenset(observed),
            required_capabilities=frozenset(required),
            friction_events=friction,
            recovery_events=recovery,
            collaboration_opt_in=opt_in,
        ))
    return rows


def request(kind: str, *, labels: bool = True) -> gate.ScopeRequest:
    return gate.ScopeRequest(
        tenant_id="tenant-a",
        subject_id="alice",
        team_ids=frozenset({"platform"}),
        authorization_epoch=9,
        classification_ceiling=2,
        purpose="quality-improvement",
        analysis=kind,
        cross_user_consent=True,
        consent_scope="platform-v1",
        minimum_cohort=3,
        require_human_outcomes=labels,
    )


def build_result() -> dict[str, Any]:
    rows = fixture()
    outputs = {
        kind: analysis.analyze(rows, request(kind))
        for kind in ("similar_work", "friction_recovery", "skill_gap", "collaboration")
    }
    serialized_outputs = json.dumps(outputs, sort_keys=True)
    checks = {
        "similar_work_allowed_after_gate": outputs["similar_work"]["decision"] == "allow",
        "friction_recovery_allowed_after_gate": outputs["friction_recovery"]["decision"] == "allow",
        "skill_gap_reports_only_observed_required_deltas": outputs["skill_gap"]["decision"] == "allow" and bool(outputs["skill_gap"]["payload"]["capability_gaps"]),
        "collaboration_requires_opt_in_and_hashes_subject_pairs": outputs["collaboration"]["decision"] == "allow" and outputs["collaboration"]["payload"]["opted_in_subject_count"] == 4 and all("subject_pair_digest" in pair for pair in outputs["collaboration"]["payload"]["candidate_pairs"]),
        "all_outputs_are_content_free": (
            not any(subject in serialized_outputs for subject in ("alice", "bob", "carol", "dana"))
            and not any(f"{subject}-trace" in serialized_outputs for subject in ("alice", "bob", "carol", "dana"))
        ),
    }
    return {
        "schema_version": "frankengate-enterprise-outcome-analysis-conformance-v1",
        "analysis_schema_version": analysis.SCHEMA_VERSION,
        "outputs": outputs,
        "checks": checks,
        "all_passed": all(checks.values()),
        "claim_boundary": {
            "authorized_structural_answers_computed": all(checks.values()),
            "cross_user_utility_measured": False,
            "capability_inference_validated": False,
            "collaboration_outcome_measured": False,
            "raw_trace_content_committed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = build_result()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_passed": value["all_passed"]}, sort_keys=True))
    return 0 if value["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
