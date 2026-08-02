#!/usr/bin/env python3
"""Measure same-user recurrence tiers for DataClaw artifact candidates.

The strict cross-user identity study found no shared identities. This companion
probe quantifies the local library signal using the existing content-free miner:
session recurrence, project recurrence, and friction-context proximity. It does
not infer correctness or promotion eligibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from dataclaw_candidate_artifact_miner import mine


SCHEMA_VERSION = "frankengate-dataclaw-same-user-artifact-support-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def summarize(path: Path, limit: int) -> dict[str, Any]:
    receipt = mine(path.resolve(strict=True), limit)
    rows = receipt["candidates"]
    total_occurrences = sum(int(row["occurrences"]) for row in rows)
    total_friction = sum(int(row["friction_context_occurrences"]) for row in rows)

    def count(predicate: Any) -> int:
        return sum(1 for row in rows if predicate(row))

    return {
        "session_count": receipt["session_count"],
        "candidate_count": len(rows),
        "candidate_limit": limit,
        "source_sha256": receipt["source_sha256"],
        "support_tiers": {
            "support_at_least_two_sessions": count(lambda row: row["support_sessions"] >= 2),
            "support_at_least_five_sessions": count(lambda row: row["support_sessions"] >= 5),
            "support_at_least_two_projects": count(lambda row: row["support_projects"] >= 2),
            "support_at_least_three_projects": count(lambda row: row["support_projects"] >= 3),
            "cross_project_and_friction_adjacent": count(lambda row: row["cross_project"] and row["friction_context_occurrences"] > 0),
            "repeated_and_friction_adjacent": count(lambda row: row["support_sessions"] >= 2 and row["friction_context_occurrences"] > 0),
        },
        "occurrence_totals": {
            "candidate_occurrences": total_occurrences,
            "friction_context_occurrences": total_friction,
            "friction_context_rate": round(total_friction / total_occurrences, 6) if total_occurrences else 0.0,
        },
        "top_support": {
            "max_sessions": max((int(row["support_sessions"]) for row in rows), default=0),
            "max_projects": max((int(row["support_projects"]) for row in rows), default=0),
            "max_occurrences": max((int(row["occurrences"]) for row in rows), default=0),
        },
        "raw_content_committed": False,
    }


def run(inputs: list[tuple[str, Path]], output: Path, limit: int) -> dict[str, Any]:
    users = {name: summarize(path, limit) for name, path in inputs}
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "users": users,
        "claim_boundary": {
            "same_user_recurrence_measured": True,
            "artifact_correctness_established": False,
            "friction_causality_established": False,
            "promotion_authorized": False,
            "reason": "Recurrence and friction proximity identify scoped review candidates only; correctness, safety, task intent, and user benefit require replay and labels.",
        },
        "raw_content_committed": False,
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(users, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", action="append", nargs=2, metavar=("NAME", "PATH"), required=True)
    parser.add_argument("--limit", type=int, default=100000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run([(name, Path(path)) for name, path in args.user], args.output, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
