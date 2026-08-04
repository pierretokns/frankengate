#!/usr/bin/env python3
"""Measure stability of contextual acronym candidates across trace cohorts.

This is a content-minimized diagnostic for the AcronymExpansion-style port. It
keeps only hashes and aggregate counts; it does not claim that a parenthetical
definition is a reviewed enterprise alias.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from modern_term_acronym_port import acronym_definitions
from term_extraction_gliner_benchmark import load_documents


SCHEMA_VERSION = "frankengate-acronym-cross-cohort-stability-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def run(roots: list[tuple[str, Path]], output: Path, max_docs: int | None = None) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    acronym_sets: dict[str, set[str]] = {}
    definition_sets: dict[str, set[tuple[str, str]]] = {}

    for name, root in roots:
        docs = load_documents(root, max_docs)
        acronym_defs: dict[str, set[str]] = defaultdict(set)
        acronym_rows: dict[str, int] = defaultdict(int)
        docs_with_definitions = 0
        for doc in docs:
            definitions = acronym_definitions(doc["text"])
            if definitions:
                docs_with_definitions += 1
            for acronym, candidates in definitions.items():
                acronym_hash = digest(acronym)
                for candidate in candidates:
                    acronym_rows[acronym_hash] += 1
                    if candidate.get("match"):
                        full_hash = str(candidate["full_hash"])
                        acronym_defs[acronym_hash].add(full_hash)

        all_acronyms = set(acronym_rows)
        valid_acronyms = set(acronym_defs)
        unambiguous = {key for key, values in acronym_defs.items() if len(values) == 1}
        ambiguous = {key for key, values in acronym_defs.items() if len(values) > 1}
        definition_pairs = {(key, value) for key, values in acronym_defs.items() for value in values}
        acronym_sets[name] = valid_acronyms
        definition_sets[name] = definition_pairs
        rows[name] = {
            "root_name": root.name,
            "document_count": len(docs),
            "documents_with_parenthetical_candidates": docs_with_definitions,
            "candidate_acronym_count": len(all_acronyms),
            "valid_acronym_count": len(valid_acronyms),
            "unambiguous_acronym_count": len(unambiguous),
            "ambiguous_acronym_count": len(ambiguous),
            "valid_definition_pair_count": len(definition_pairs),
            "raw_content_committed": False,
        }

    pairwise: dict[str, dict[str, Any]] = {}
    names = sorted(acronym_sets)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            shared_acronyms = acronym_sets[left] & acronym_sets[right]
            shared_definitions = definition_sets[left] & definition_sets[right]
            key = f"{left}__{right}"
            pairwise[key] = {
                "left": left,
                "right": right,
                "shared_valid_acronyms": len(shared_acronyms),
                "shared_exact_definition_pairs": len(shared_definitions),
                "definition_agreement_given_shared_acronym": round(
                    len(shared_definitions) / len(shared_acronyms), 6
                ) if shared_acronyms else None,
            }

    frequency: dict[str, int] = defaultdict(int)
    for values in acronym_sets.values():
        for value in values:
            frequency[value] += 1
    definition_frequency: dict[tuple[str, str], int] = defaultdict(int)
    for values in definition_sets.values():
        for value in values:
            definition_frequency[value] += 1

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "cohorts": rows,
        "pairwise": pairwise,
        "valid_acronym_cohort_frequency": {
            "one_cohort": sum(value == 1 for value in frequency.values()),
            "two_or_more_cohorts": sum(value >= 2 for value in frequency.values()),
            "all_cohorts": sum(value == len(names) for value in frequency.values()),
            "unique_acronyms": len(frequency),
        },
        "exact_definition_pair_cohort_frequency": {
            "one_cohort": sum(value == 1 for value in definition_frequency.values()),
            "two_or_more_cohorts": sum(value >= 2 for value in definition_frequency.values()),
            "all_cohorts": sum(value == len(names) for value in definition_frequency.values()),
            "unique_pairs": len(definition_frequency),
        },
        "claim_boundary": {
            "alias_quality": False,
            "enterprise_concept_quality": False,
            "semantic_equivalence": False,
            "reason": "Parenthetical acronym extraction measures candidate stability only; exact shared strings may be boilerplate, and absent definitions do not prove an acronym is invalid.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cohorts": rows, "valid_frequency": result["valid_acronym_cohort_frequency"]}, sort_keys=True))
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
