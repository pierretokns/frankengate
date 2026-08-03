#!/usr/bin/env python3
"""Decide whether the gap-mining workload has earned a ClickHouse projection.

This is a measured gate, not a database preference.  The metrics should come
from the real log store (or a replay benchmark), and the thresholds are
explicit configuration so they can be changed without changing the detector.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_THRESHOLDS = {
    "max_p95_scan_seconds": 10.0,
    "max_source_bytes": 500_000_000_000,
    "max_daily_scans": 100,
}


def assess_clickhouse_need(
    metrics: Mapping[str, Any],
    thresholds: Mapping[str, float | int] = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """Return a transparent recommendation from measured workload metrics."""

    reasons: list[str] = []
    p95 = float(metrics.get("p95_scan_seconds", 0.0))
    source_bytes = int(metrics.get("source_bytes", 0))
    daily_scans = int(metrics.get("daily_gap_scans", 0))
    if p95 > float(thresholds["max_p95_scan_seconds"]):
        reasons.append("p95 gap scan latency exceeds the configured budget")
    if source_bytes > int(thresholds["max_source_bytes"]):
        reasons.append("source log volume exceeds the configured analytical-store budget")
    if daily_scans > int(thresholds["max_daily_scans"]):
        reasons.append("repeated daily scans justify a pre-aggregated projection")
    decision = "clickhouse_candidate" if reasons else "postgres_first"
    return {
        "schema_version": "frankengate-wiki-gap-backend-assessment-v1",
        "decision": decision,
        "reasons": reasons,
        "metrics": {
            "event_count": int(metrics.get("event_count", 0)),
            "source_bytes": source_bytes,
            "p95_scan_seconds": p95,
            "daily_gap_scans": daily_scans,
        },
        "thresholds": dict(thresholds),
        "next_step": (
            "run the ClickHouse projection benchmark against the same replay cohort"
            if reasons
            else "continue with PostgreSQL and collect the same metrics in production"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metrics = json.loads(args.metrics_json.read_text(encoding="utf-8"))
    result = assess_clickhouse_need(metrics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
