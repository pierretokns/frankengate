#!/usr/bin/env python3
"""Create a content-free receipt for the guarded H5 PostgreSQL rerun.

The guard is deliberately a separate receipt from the original rerun: it
adds a fail-closed transaction contract while preserving the original race
invariants.  The comparison ignores only the SQL hash and the new guard
field, never the observed race or cleanup assertions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-h5-concurrency-guarded-rerun-check-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def comparable(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: comparable(item)
            for key, item in value.items()
            if key not in {
                "elapsed_ms",
                "reader_elapsed_ms",
                "mutation_elapsed_ms",
                "sql_sha256",
                "governed_isolation_guard",
            }
        }
    if isinstance(value, list):
        return [comparable(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", type=Path, required=True)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    live = json.loads(args.live.read_text(encoding="utf-8"))
    prior = json.loads(args.prior.read_text(encoding="utf-8"))
    guard = live.get("governed_isolation_guard", {})
    checks = {
        "overall_mechanics_passed": live.get("overall") == "mechanics_passed_with_architecture_gaps",
        "content_free_assertions_passed": live.get("content_free_and_role_assertions") == "passed",
        "cleanup_zero_residue": live.get("cleanup", {}).get("marker") == "H5C_ZERO_RESIDUE_OK"
        and live.get("cleanup", {}).get("fixture_rows") == 0,
        "nine_race_observations": len(live.get("races", [])) == 9,
        "known_architecture_gaps_preserved": len(live.get("known_gaps", [])) >= 6,
        "invariant_match_to_prior": comparable(live) == comparable(prior),
        "governed_repeatable_read_rejected": (
            guard.get("repeatable_read_rejected") is True
            and guard.get("required_isolation") == "read committed"
            and guard.get("failure") == "governed queries require READ COMMITTED; repeatable read rejected"
        ),
        "raw_trace_content_not_loaded": live.get("raw_trace_content_loaded") is False,
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "date": "2026-08-02",
        "runner": "research/trace-intelligence/tests/run_trace_commons_memory_h5_concurrency.py --timeout 30",
        "live_result_sha256": sha256(args.live),
        "prior_result_sha256": sha256(args.prior),
        "checks": checks,
        "all_passed": all(checks.values()),
        "live_summary": {
            "overall": live.get("overall"),
            "postgresql": live.get("lab", {}).get("postgresql_version"),
            "pgvector": live.get("lab", {}).get("pgvector_version"),
            "races": len(live.get("races", [])),
            "known_gaps": len(live.get("known_gaps", [])),
            "cleanup_marker": live.get("cleanup", {}).get("marker"),
            "governed_isolation": "read committed",
            "repeatable_read_rejected": guard.get("repeatable_read_rejected") is True,
        },
        "claim_boundary": "Live local PostgreSQL/pgvector RLS concurrency rerun plus a fail-closed READ COMMITTED guard; no managed Aurora, RDS Proxy, failover, PITR, or scale claim.",
        "content_policy": {
            "raw_trace_content_emitted": False,
            "raw_live_result_embedded": False,
        },
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
