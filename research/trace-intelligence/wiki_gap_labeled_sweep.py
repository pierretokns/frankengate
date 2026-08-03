#!/usr/bin/env python3
"""Run the labeled wiki-gap detector over several cohort sizes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from wiki_gap_labeled_experiment import build_cohort, evaluate


def run_sweep(sizes: list[int]) -> dict[str, object]:
    rows = []
    for size in sizes:
        events, pages, gold = build_cohort(size)
        result = evaluate(events, pages, gold)
        rows.append(
            {
                "per_stratum": size,
                "events": len(events),
                "queries": len(gold),
                "precision": result["precision"],
                "recall": result["recall"],
                "f1": result["f1"],
                "false_positive_count": result["false_positive_count"],
                "false_negative_count": result["false_negative_count"],
            }
        )
    return {
        "schema_version": "frankengate-wiki-gap-labeled-sweep-v1",
        "sizes": rows,
        "interpretation": "Controlled cohort-size stability only; not evidence of production prevalence or human-label agreement.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="1,3,10,20,50,100")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sizes = [int(value) for value in args.sizes.split(",") if value.strip()]
    result = run_sweep(sizes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
