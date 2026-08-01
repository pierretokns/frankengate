#!/usr/bin/env python3
"""Mine a conservative surface-to-schema alias baseline from NL2SQL rows.

Only exact morphological variants are linked (singular/plural and underscore
normalization). This intentionally measures a lower bound and ambiguity
surface, not semantic alias truth. The committed result contains hashes and
counts, never questions, SQL, or identifier strings.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
TABLE_RE = re.compile(r"\b(?:from|join|update|into)\s+([\"`A-Za-z_][\w$.\"`]*)", re.I)
QUALIFIED_RE = re.compile(r"\b([A-Za-z_][\w$]*)\.([A-Za-z_][\w$]*)\b")
SQL_WORDS = {
    "select", "from", "where", "join", "left", "right", "inner", "outer", "full",
    "on", "and", "or", "as", "group", "by", "order", "having", "limit", "offset",
    "with", "union", "all", "distinct", "case", "when", "then", "else", "end",
    "asc", "desc", "null", "is", "not", "in", "exists", "between", "like",
    "true", "false", "count", "sum", "avg", "min", "max", "coalesce", "cast",
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def normalize(value: str) -> str:
    value = value.strip('"`').lower().replace("_", "")
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if value.endswith("es") and len(value) > 4:
        return value[:-2]
    if value.endswith("s") and len(value) > 3:
        return value[:-1]
    return value


def canonical_identifiers(sql: str) -> set[str]:
    identifiers: set[str] = set()
    for match in TABLE_RE.finditer(sql):
        value = match.group(1).strip('"`').split()[0]
        if value:
            identifiers.add(value.lower())
    for left, right in QUALIFIED_RE.findall(sql):
        if left.lower() not in SQL_WORDS and right.lower() not in SQL_WORDS:
            identifiers.add(right.lower())
            identifiers.add(left.lower())
    return identifiers


def surface_tokens(question: str) -> set[str]:
    return {
        token.lower()
        for token in WORD_RE.findall(question)
        if token.lower() not in SQL_WORDS
    }


def analyze(source: Path) -> dict[str, Any]:
    mappings: dict[str, set[tuple[str, str]]] = defaultdict(set)
    db_surfaces: dict[str, set[str]] = defaultdict(set)
    rows = rows_with_sql = link_count = 0
    with source.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            question = row.get("question", "")
            sql = row.get("query", "")
            db = row.get("db_name", "")
            identifiers = canonical_identifiers(sql)
            if not identifiers:
                continue
            rows_with_sql += 1
            surfaces = surface_tokens(question)
            canonical_by_norm: dict[str, set[str]] = defaultdict(set)
            for identifier in identifiers:
                canonical_by_norm[normalize(identifier)].add(identifier)
            for surface in surfaces:
                canonical = canonical_by_norm.get(normalize(surface), set())
                for identifier in canonical:
                    mappings[digest(surface)].add((db, digest(identifier)))
                    db_surfaces[digest(surface)].add(db)
                    link_count += 1

    ambiguous = {
        key: values for key, values in mappings.items() if len(values) > 1
    }
    same_db_ambiguous = sum(
        len({db for db, _ in values}) < len(values) for values in ambiguous.values()
    )
    cross_db_ambiguous = sum(
        len({db for db, _ in values}) > 1 for values in ambiguous.values()
    )
    return {
        "schema_version": "nl2sql-alias-mining-v1",
        "source": {"path": source.name, "raw_content_committed": False},
        "rows": rows,
        "rows_with_qualified_or_table_sql": rows_with_sql,
        "surface_to_identifier_links": link_count,
        "unique_surface_hashes": len(mappings),
        "ambiguous_surface_hashes": len(ambiguous),
        "same_db_ambiguity_hashes": same_db_ambiguous,
        "cross_db_ambiguity_hashes": cross_db_ambiguous,
        "top_surface_hashes_by_distinct_canonical": [
            {"surface_hash": key, "distinct_canonical": len(values)}
            for key, values in sorted(
                mappings.items(), key=lambda item: (-len(item[1]), item[0])
            )[:20]
        ],
        "claim_boundary": (
            "Conservative exact-morphology lower bound only. Hashes identify "
            "collision classes without exposing questions or schema identifiers; "
            "semantic aliases, NIL mentions, and business meaning require review."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
