#!/usr/bin/env python3
"""Profile public BIRD-Interact ambiguity and follow-up labels.

The public task file intentionally omits gold SQL and executable test cases.
This script measures only the released ambiguity/follow-up structure, keeping
raw queries out of the receipt.  It is a dataset-fit and cohort-construction
probe, not an agent-quality benchmark.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-interact-ambiguity-profile-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def profile(path: Path, output: Path) -> dict[str, Any]:
    databases: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    follow_up_types: Counter[str] = Counter()
    critical_types: Counter[str] = Counter()
    noncritical_types: Counter[str] = Counter()
    knowledge_types: Counter[str] = Counter()
    output_types: Counter[str] = Counter()
    records = 0
    records_with_critical = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            records += 1
            databases[str(row.get("selected_database", "unknown"))] += 1
            categories[str(row.get("category", "unknown"))] += 1
            output_types[str(row.get("output_type", "unknown"))] += 1
            ambiguity = row.get("user_query_ambiguity") or {}
            critical_items = ambiguity.get("critical_ambiguity") or []
            records_with_critical += int(bool(critical_items))
            for item in critical_items:
                critical_types[str(item.get("type", "unknown"))] += 1
            for item in ambiguity.get("non_critical_ambiguity") or []:
                noncritical_types[str(item.get("type", "unknown"))] += 1
            for item in row.get("knowledge_ambiguity") or []:
                knowledge_types[str(item.get("type", "unknown"))] += 1
            follow_up = row.get("follow_up")
            if isinstance(follow_up, dict):
                follow_up_types[str(follow_up.get("type", "unknown"))] += 1
            else:
                follow_up_types["none"] += 1

    total_critical = sum(critical_types.values())
    total_noncritical = sum(noncritical_types.values())
    total_knowledge = sum(knowledge_types.values())
    follow_up_count = records - follow_up_types.get("none", 0)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "dataset_id": "birdsql/bird-interact-full",
            "revision": "5d78b0722433c3821e1ebda5d8c39d24070049d7",
            "file_sha256": sha256_file(path),
            "records": records,
            "raw_content_committed": False,
            "gold_sql_and_test_cases_available": False,
        },
        "aggregate": {
            "databases": dict(sorted(databases.items())),
            "categories": dict(sorted(categories.items())),
            "output_types": dict(sorted(output_types.items())),
            "follow_up_types": dict(sorted(follow_up_types.items())),
            "critical_ambiguity_types": dict(sorted(critical_types.items())),
            "noncritical_ambiguity_types": dict(sorted(noncritical_types.items())),
            "knowledge_ambiguity_types": dict(sorted(knowledge_types.items())),
            "records_with_follow_up": follow_up_count,
            "records_with_critical_ambiguity": records_with_critical,
            "critical_ambiguity_annotations": total_critical,
            "noncritical_ambiguity_annotations": total_noncritical,
            "knowledge_ambiguity_annotations": total_knowledge,
        },
        "claim_boundary": {
            "clarification_cohort_profiled": True,
            "friction_or_agent_quality_measured": False,
            "natural_human_interaction_established": False,
            "independent_outcome_measured": False,
            "reason": "Public BIRD-Interact labels describe injected ambiguity and follow-up structure; gold SQL, tests, and simulator outcomes are not present in the released task file.",
        },
    }
    receipt["result_sha256"] = hashlib.sha256(stable_json(receipt)).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["aggregate"], sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile(args.input.resolve(strict=True), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
