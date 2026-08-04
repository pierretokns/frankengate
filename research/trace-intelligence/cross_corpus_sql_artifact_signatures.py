#!/usr/bin/env python3
"""Measure structural SQL-artifact overlap across BIRD and Defog.

The probe separates exact normalized templates (identifiers retained) from
schema-agnostic templates (tables/columns anonymized). It never treats a
schema-agnostic match as executable reuse; the collision metrics quantify why
that would be unsafe. Only hashes and aggregate counts are written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one

from bird_trace_artifact_reuse import load_tasks


SCHEMA_VERSION = "frankengate-cross-corpus-sql-artifact-signatures-v1"


@dataclass(frozen=True)
class QueryRow:
    corpus: str
    row_key: str
    sql: str
    dialect: str
    source_valid: bool


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _table_maps(parsed: exp.Expression) -> tuple[dict[str, str], dict[str, str]]:
    table_names: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for node in parsed.find_all(exp.Table):
        table_name = str(node.name or "").lower()
        if table_name and table_name not in table_names:
            table_names[table_name] = f"T{len(table_names) + 1}"
        alias = str(node.alias or "").lower()
        if alias and alias not in aliases:
            aliases[alias] = table_names.get(table_name, f"T{len(table_names) + 1}")
    return table_names, aliases


def signature(sql: str, dialect: str, anonymize_identifiers: bool) -> str:
    parsed = parse_one(sql, read=dialect)
    table_names, aliases = _table_maps(parsed)
    column_names: dict[tuple[str, str], str] = {}

    def transform(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Literal):
            return exp.Placeholder()
        if isinstance(node, exp.Table):
            table_name = str(node.name or "").lower()
            generic = table_names.get(table_name, "T1")
            node = node.copy()
            node.set("this", exp.Identifier(this=generic))
            node.set("alias", None)
            return node
        if isinstance(node, exp.Column):
            node = node.copy()
            source = str(node.table or "").lower()
            qualifier = aliases.get(source, source)
            name = str(node.name or "").lower()
            key = (qualifier, name)
            if anonymize_identifiers:
                if key not in column_names:
                    column_names[key] = f"C{len(column_names) + 1}"
                node.set("this", exp.Identifier(this=column_names[key]))
            else:
                node.set("this", exp.Identifier(this=name))
            if qualifier:
                node.set("table", exp.Identifier(this=qualifier))
            return node
        if isinstance(node, exp.Alias):
            node = node.copy()
            node.set("alias", None)
            return node
        return node

    normalized = parsed.transform(transform)
    return normalized.sql(dialect="sqlite", pretty=False).lower()


def coarse_signature(sql: str, dialect: str) -> str:
    """Return an intentionally permissive operator-shape signature.

    This is an upper-bound candidate generator: it preserves the multiset of
    AST node types and therefore deliberately admits many false matches.
    """
    parsed = parse_one(sql, read=dialect)
    counts = Counter(type(node).__name__ for node in parsed.walk())
    return ";".join(f"{name}:{counts[name]}" for name in sorted(counts))


def load_bird(root: Path) -> tuple[list[QueryRow], dict[str, Any]]:
    rows: list[QueryRow] = []
    tasks = load_tasks(root)
    parse_failures = 0
    for task_id, task in tasks.items():
        valid = False
        try:
            parse_one(task.gold_sql, read="sqlite")
            valid = True
        except Exception:
            parse_failures += 1
        rows.append(QueryRow("bird", sha256_text(task_id), task.gold_sql, "sqlite", valid))
    return rows, {"rows": len(rows), "parse_failures": parse_failures}


def load_defog(root: Path) -> tuple[list[QueryRow], dict[str, Any]]:
    rows: list[QueryRow] = []
    parse_failures = 0
    for filename in ("instruct_basic_postgres.csv", "instruct_advanced_postgres.csv", "questions_gen_postgres.csv"):
        path = root / "data" / filename
        with path.open(newline="", encoding="utf-8") as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                sql = str(row.get("query", "")).strip()
                key = f"{filename}:{index}:{row.get('db_name', '')}"
                try:
                    parse_one(sql, read="postgres")
                    valid = True
                except Exception:
                    valid = False
                    parse_failures += 1
                rows.append(QueryRow("defog", sha256_text(key), sql, "postgres", valid))
    return rows, {"rows": len(rows), "parse_failures": parse_failures}


def run(bird_root: Path, defog_root: Path, output: Path) -> dict[str, Any]:
    bird, bird_meta = load_bird(bird_root)
    defog, defog_meta = load_defog(defog_root)
    all_rows = bird + defog
    exact: dict[str, list[str]] = defaultdict(list)
    structural: dict[str, list[str]] = defaultdict(list)
    coarse: dict[str, list[str]] = defaultdict(list)
    per_corpus: dict[str, dict[str, Counter[str]]] = {
        "bird": {"exact": Counter(), "structural": Counter(), "coarse": Counter()},
        "defog": {"exact": Counter(), "structural": Counter(), "coarse": Counter()},
    }
    parse_failures = 0
    for row in all_rows:
        if not row.source_valid:
            parse_failures += 1
            continue
        try:
            exact_sig = signature(row.sql, row.dialect, False)
            structural_sig = signature(row.sql, row.dialect, True)
            coarse_sig = coarse_signature(row.sql, row.dialect)
        except Exception:
            parse_failures += 1
            continue
        exact[exact_sig].append(row.corpus)
        structural[structural_sig].append(row.corpus)
        coarse[coarse_sig].append(row.corpus)
        per_corpus[row.corpus]["exact"][exact_sig] += 1
        per_corpus[row.corpus]["structural"][structural_sig] += 1
        per_corpus[row.corpus]["coarse"][coarse_sig] += 1

    def shared(mapping: dict[str, list[str]]) -> set[str]:
        return {key for key, values in mapping.items() if "bird" in values and "defog" in values}

    shared_exact = shared(exact)
    shared_structural = shared(structural)
    shared_coarse = shared(coarse)
    ambiguous_structural = {
        key for key in shared_structural
        if len({digest(value) for value in [key]}) >= 1 and len(exact.get(key, [])) > 1
    }
    # The exact signature is not the structural key, so compute collision risk
    # by grouping exact signatures under each structural signature.
    structural_to_exact: dict[str, set[str]] = defaultdict(set)
    coarse_to_exact: dict[str, set[str]] = defaultdict(set)
    for row in all_rows:
        if not row.source_valid:
            continue
        try:
            exact_sig = signature(row.sql, row.dialect, False)
            structural_sig = signature(row.sql, row.dialect, True)
            coarse_sig = coarse_signature(row.sql, row.dialect)
        except Exception:
            continue
        structural_to_exact[structural_sig].add(exact_sig)
        coarse_to_exact[coarse_sig].add(exact_sig)
    ambiguous_structural = {
        key for key in shared_structural if len(structural_to_exact.get(key, set())) > 1
    }
    ambiguous_coarse = {
        key for key in shared_coarse if len(coarse_to_exact.get(key, set())) > 1
    }
    target_rows_with_structural_source = sum(
        1 for row in defog if row.source_valid and any(
            corpus == "bird" for corpus in structural.get(
                signature(row.sql, row.dialect, True), []
            )
        )
    )
    target_rows_with_coarse_source = sum(
        1 for row in defog if row.source_valid and any(
            corpus == "bird" for corpus in coarse.get(
                coarse_signature(row.sql, row.dialect), []
            )
        )
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "sources": {
            "bird": {"root": "world-model-harness-bird-sql", **bird_meta},
            "defog": {"root": "defog-sql-eval-research", **defog_meta},
        },
        "parse_valid_rows": {
            corpus: sum(1 for row in rows if row.source_valid)
            for corpus, rows in (("bird", bird), ("defog", defog))
        },
        "template_counts": {
            corpus: {
                "unique_exact_templates": len(per_corpus[corpus]["exact"]),
                "unique_structural_templates": len(per_corpus[corpus]["structural"]),
                "unique_coarse_operator_shapes": len(per_corpus[corpus]["coarse"]),
            }
            for corpus in ("bird", "defog")
        },
        "cross_corpus_overlap": {
            "shared_exact_templates": len(shared_exact),
            "shared_structural_templates": len(shared_structural),
            "shared_structural_with_multiple_exact_variants": len(ambiguous_structural),
            "structural_collision_rate": round(
                len(ambiguous_structural) / len(shared_structural), 6
            ) if shared_structural else None,
            "defog_rows_with_bird_structural_match": target_rows_with_structural_source,
            "shared_coarse_operator_shapes": len(shared_coarse),
            "shared_coarse_with_multiple_exact_variants": len(ambiguous_coarse),
            "coarse_collision_rate": round(
                len(ambiguous_coarse) / len(shared_coarse), 6
            ) if shared_coarse else None,
            "defog_rows_with_bird_coarse_match": target_rows_with_coarse_source,
        },
        "parse_or_execution_failures_during_signature": parse_failures,
        "claim_boundary": {
            "schema_agnostic_overlap_measured": True,
            "cross_corpus_executable_reuse_established": False,
            "semantic_intent_transfer_established": False,
            "reason": "Schema-agnostic signatures are structural candidate-generation signals; they do not carry identifiers, authority, dialect, schema compatibility, or result validators.",
        },
        "raw_content_committed": False,
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["cross_corpus_overlap"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bird-root", type=Path, required=True)
    parser.add_argument("--defog-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.bird_root.resolve(strict=True), args.defog_root.resolve(strict=True), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
