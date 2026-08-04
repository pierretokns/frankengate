#!/usr/bin/env python3
"""Independent, content-free verifier for the natural release receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-natural-released-procedure-verification-v1"


def verify(result: dict[str, Any]) -> dict[str, Any]:
    aggregate = result.get("aggregate", {})
    rows = result.get("project_rows", [])
    verifier_rows = result.get("verifier_rows", [])
    checks = {
        "schema_version": result.get("schema_version") == "frankengate-natural-released-procedure-v1",
        "projects_have_matching_rows": len(rows) == len(verifier_rows) == aggregate.get("projects_with_release"),
        "all_projects_have_release": all(row.get("expert_release_before_first_query") for row in rows),
        "all_proposals_verified": all(row.get("proposal_status") == "released" for row in rows),
        "all_lineage_checks_passed": all(row.get("checks_passed") for row in verifier_rows),
        "all_verifier_verdicts_verified": all(row.get("verification_verdict") == "verified" for row in verifier_rows),
        "visible_count_matches_queries": aggregate.get("visible_procedure_query_count") == aggregate.get("admitted_queries"),
        "no_raw_content_policy": result.get("content_policy", {}).get("raw_content_emitted") is False,
        "no_paths_policy": result.get("content_policy", {}).get("paths_emitted") is False,
        "utility_not_overclaimed": result.get("claim_boundary", {}).get("procedure_quality_confirmed") is False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt": "natural-released-procedure-2026-08-02.json",
        "all_passed": all(checks.values()),
        "checks": checks,
        "projects_verified": len(verifier_rows),
        "queries_verified": aggregate.get("admitted_queries", 0),
        "content_policy": {
            "raw_result_content_read": False,
            "raw_result_content_emitted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.receipt.read_text(encoding="utf-8"))
    verification = verify(result)
    args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, sort_keys=True))
    return 0 if verification["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
