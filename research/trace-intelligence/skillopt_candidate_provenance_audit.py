#!/usr/bin/env python3
"""Audit candidate-file provenance across Codex SkillOpt transfer receipts.

The audit prevents an empty candidate from being described as a meaningful
negative skill intervention.  It reports only hashes, lengths, and aggregate
outcomes; candidate text is never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-skillopt-candidate-provenance-audit-v1"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--receipt", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate = args.candidate.read_text(encoding="utf-8")
    candidate_hash = sha256_text(candidate)
    rows: list[dict[str, Any]] = []
    for path in args.receipt:
        value = json.loads(path.read_text(encoding="utf-8"))
        observed = value.get("candidate_sha256")
        rows.append(
            {
                "receipt": path.name,
                "candidate_sha256": observed,
                "candidate_length": len(candidate) if observed == candidate_hash else None,
                "matches_real_candidate": observed == candidate_hash,
                "empty_candidate": observed == sha256_text(""),
                "summary": value.get("summary", {}),
            }
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "candidate_sha256": candidate_hash,
        "candidate_length": len(candidate),
        "rows": rows,
        "checks": {
            "real_candidate_receipt_present": any(row["matches_real_candidate"] for row in rows),
            "empty_candidate_rows_explicitly_identified": all(
                not row["empty_candidate"] or row["candidate_length"] is None
                for row in rows
            ),
        },
        "claim_boundary": {
            "r20_r21_empty_candidate_rows_not_skill_quality_evidence": any(
                row["empty_candidate"] for row in rows
            ),
            "r22_real_candidate_is_the_corrected_transfer_arm": any(
                "r22" in row["receipt"] and row["matches_real_candidate"] for row in rows
            ),
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
        },
        "raw_content_policy": {
            "candidate_text_emitted": False,
            "model_responses_emitted": False,
        },
    }
    result["all_passed"] = all(result["checks"].values())
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_passed": result["all_passed"], "rows": len(rows)}, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
