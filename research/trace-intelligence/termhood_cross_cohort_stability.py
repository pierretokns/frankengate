#!/usr/bin/env python3
"""Measure cross-cohort stability of deterministic vocabulary candidates.

This is a corpus-stability diagnostic, not an alias-quality benchmark. It
keeps only hashes/counts and asks whether top terms recur across independent
trace cohorts or remain local to one corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from term_extraction_gliner_benchmark import deterministic_terms, load_documents


SCHEMA_VERSION = "frankengate-termhood-cross-cohort-stability-v1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def run(roots: list[tuple[str, Path]], output: Path, max_docs: int | None = None) -> dict[str, Any]:
    cohort_rows: dict[str, dict[str, Any]] = {}
    top_sets: dict[str, set[str]] = {}
    for name, root in roots:
        docs = load_documents(root, max_docs)
        summary = deterministic_terms(docs)
        top_sets[name] = set(summary["top_term_hashes"])
        cohort_rows[name] = {
            "root_name": root.name,
            "document_count": summary["document_count"],
            "unique_term_count": summary["unique_term_count"],
            "acronym_count": summary["acronym_count"],
            "reformulation_candidate_count": summary["reformulation_candidate_count"],
            "top_term_count": len(summary["top_term_hashes"]),
            "top_term_hashes": summary["top_term_hashes"],
            "raw_content_committed": False,
        }

    pairwise: dict[str, dict[str, Any]] = {}
    names = sorted(top_sets)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            intersection = top_sets[left] & top_sets[right]
            union = top_sets[left] | top_sets[right]
            key = f"{left}__{right}"
            pairwise[key] = {
                "left": left,
                "right": right,
                "shared_top_terms": len(intersection),
                "jaccard_top_terms": round(len(intersection) / len(union), 6) if union else 0.0,
            }
    cohort_frequency: Counter[str] = Counter()
    for values in top_sets.values():
        cohort_frequency.update(values)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "cohorts": cohort_rows,
        "pairwise_top_term_overlap": pairwise,
        "top_terms_by_cohort_frequency": {
            "one_cohort": sum(count == 1 for count in cohort_frequency.values()),
            "two_or_more_cohorts": sum(count >= 2 for count in cohort_frequency.values()),
            "all_cohorts": sum(count == len(names) for count in cohort_frequency.values()),
            "unique_top_hashes": len(cohort_frequency),
        },
        "claim_boundary": {
            "alias_quality": False,
            "enterprise_concept_quality": False,
            "semantic_equivalence": False,
            "reason": "Top-term overlap measures corpus stability only; shared terms may be harness boilerplate and cohort-specific terms may be valid corporate concepts or noise.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cohorts": {name: {k: row[k] for k in ("document_count", "unique_term_count", "top_term_count")} for name, row in cohort_rows.items()}, "overlap": result["top_terms_by_cohort_frequency"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", nargs=2, metavar=("NAME", "ROOT"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-docs", type=int)
    args = parser.parse_args()
    run([(name, Path(root)) for name, root in args.source], args.output, args.max_docs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
