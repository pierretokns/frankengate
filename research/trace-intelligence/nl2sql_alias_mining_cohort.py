#!/usr/bin/env python3
"""Combine hash-only alias-mining receipts for a fixed NL2SQL cohort."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def combine(paths: list[Path]) -> dict[str, object]:
    results = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    return {
        "schema_version": "nl2sql-alias-mining-cohort-v1",
        "source_files": [result["source"]["path"] for result in results],
        "rows": sum(int(result["rows"]) for result in results),
        "rows_with_qualified_or_table_sql": sum(
            int(result["rows_with_qualified_or_table_sql"]) for result in results
        ),
        "surface_to_identifier_links": sum(
            int(result["surface_to_identifier_links"]) for result in results
        ),
        "unique_surface_hashes_sum_by_file": sum(
            int(result["unique_surface_hashes"]) for result in results
        ),
        "ambiguous_surface_hashes_sum": sum(
            int(result["ambiguous_surface_hashes"]) for result in results
        ),
        "same_db_ambiguity_hashes_sum": sum(
            int(result["same_db_ambiguity_hashes"]) for result in results
        ),
        "cross_db_ambiguity_hashes_sum": sum(
            int(result["cross_db_ambiguity_hashes"]) for result in results
        ),
        "claim_boundary": (
            "Conservative exact-morphology lower bound only. Source receipts "
            "contain hashes and counts, not questions, SQL, or identifier strings."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = combine(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
