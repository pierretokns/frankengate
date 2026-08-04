#!/usr/bin/env python3
"""Compare command-artifact transfer across public Claude cohorts.

This composes the native Claude parser from the normalization audit and
measures whether an artifact observed successfully in one cohort appears in a
different cohort. It is an overlap/operational-prior study, not a claim that
the users had the same intent or authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from claude_command_artifact_normalization_audit import (
    parse_paths,
    representation_metrics,
    sha256_file,
    sha256_text,
)


SCHEMA_VERSION = "frankengate-claude-cross-cohort-command-transfer-v1"


def transfer_metrics(rows: list[dict[str, str]], representation: str) -> dict[str, Any]:
    source_successes: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row["outcome"] == "success":
            source_successes[row[f"{representation}_hash"]].add(row["cohort"])
    eligible = [
        row
        for row in rows
        if source_successes.get(row[f"{representation}_hash"], set()) - {row["cohort"]}
    ]
    successes = sum(row["outcome"] == "success" for row in eligible)
    artifacts = {key: cohorts for key, cohorts in source_successes.items() if len(cohorts) > 1}
    return {
        "cross_cohort_artifact_count": len(artifacts),
        "eligible_occurrences": len(eligible),
        "eligible_successes": successes,
        "eligible_failures": len(eligible) - successes,
        "cross_cohort_success_rate": round(successes / len(eligible), 6) if eligible else 0.0,
        "cohort_count_distribution": sorted(len(cohorts) for cohorts in artifacts.values()),
    }


def run(roots: list[tuple[str, Path]], output: Path) -> dict[str, Any]:
    all_rows: list[dict[str, str]] = []
    source_receipts: list[dict[str, Any]] = []
    for cohort, root in roots:
        paths = sorted(root.rglob("*.jsonl"))
        rows = parse_paths(paths)
        for row in rows:
            row["cohort"] = cohort
        all_rows.extend(rows)
        source_receipts.append({
            "cohort": cohort,
            "root_name": root.name,
            "path_count": len(paths),
            "path_sha256": sha256_text("\n".join(sha256_file(path) for path in paths)),
            "labeled_occurrences": len(rows),
        })
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "sources": source_receipts,
        "cohorts": {
            cohort: {
                "exact": representation_metrics([row for row in all_rows if row["cohort"] == cohort], "exact"),
                "normalized": representation_metrics([row for row in all_rows if row["cohort"] == cohort], "normalized"),
            }
            for cohort, _ in roots
        },
        "combined": {
            "labeled_occurrences": len(all_rows),
            "cohort_count": len(roots),
            "exact": representation_metrics(all_rows, "exact"),
            "normalized": representation_metrics(all_rows, "normalized"),
        },
        "cross_cohort_transfer": {
            "exact": transfer_metrics(all_rows, "exact"),
            "normalized": transfer_metrics(all_rows, "normalized"),
        },
        "claim_boundary": {
            "user_intent_labels": False,
            "authority_labels": False,
            "semantic_equivalence": False,
            "causal_transfer": False,
            "reason": "Cross-cohort overlap and native tool outcomes measure operational association only; identical commands do not establish shared intent, authorization, or safe reuse.",
        },
    }
    result["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["cross_cohort_transfer"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", nargs=2, metavar=("NAME", "ROOT"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run([(name, Path(root)) for name, root in args.source], args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
