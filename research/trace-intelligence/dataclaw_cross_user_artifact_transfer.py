#!/usr/bin/env python3
"""Measure strict recurring-artifact overlap across DataClaw users.

The existing two-user audit reports broad normalized tool-call overlap. This
probe uses the stricter candidate identity from the content-free artifact
miner (tool plus normalized non-trivial input) and keeps only hashes/counts.
Shared identity is a transfer candidate, never proof of correctness or shared
intent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from dataclaw_candidate_artifact_miner import mine


SCHEMA_VERSION = "frankengate-dataclaw-cross-user-artifact-transfer-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def run(inputs: list[tuple[str, Path]], output: Path, limit: int) -> dict[str, Any]:
    users: dict[str, dict[str, Any]] = {}
    identities: dict[str, set[str]] = {}
    for name, path in inputs:
        receipt = mine(path.resolve(strict=True), limit)
        rows = receipt["candidates"]
        identities[name] = {str(row["candidate_id"]) for row in rows}
        users[name] = {
            "session_count": receipt["session_count"],
            "candidate_count": len(rows),
            "cross_project_candidate_count": sum(bool(row["cross_project"]) for row in rows),
            "candidate_with_friction_context_count": sum(row["friction_context_occurrences"] > 0 for row in rows),
            "source_sha256": receipt["source_sha256"],
            "candidate_limit": limit,
            "raw_content_committed": False,
        }

    names = sorted(identities)
    pairwise: dict[str, dict[str, Any]] = {}
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            shared = identities[left] & identities[right]
            union = identities[left] | identities[right]
            pairwise[f"{left}__{right}"] = {
                "left": left,
                "right": right,
                "left_candidate_count": len(identities[left]),
                "right_candidate_count": len(identities[right]),
                "shared_strict_artifact_identities": len(shared),
                "union_strict_artifact_identities": len(union),
                "strict_identity_jaccard": round(len(shared) / len(union), 6) if union else 0.0,
            }

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "users": users,
        "pairwise": pairwise,
        "claim_boundary": {
            "strict_identity_overlap_measured": True,
            "shared_task_intent_established": False,
            "artifact_correctness_established": False,
            "cross_user_promotion_authorized": False,
            "reason": "Strict candidate identity measures reusable-call candidates only; it does not establish task equivalence, safety, authority, outcome quality, or user benefit.",
        },
        "raw_content_committed": False,
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"users": users, "pairwise": pairwise}, sort_keys=True))
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
