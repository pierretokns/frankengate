#!/usr/bin/env python3
"""Build a content-free, schema-family replay manifest from pinned Defog CSVs.

The output contains only source coordinates and hashes. Questions, SQL, and
instructions remain in the external pinned source checkout and never enter Git.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
SEED = 20260730
ENTERPRISE_DATABASES = (
    "broker",
    "car_dealership",
    "derm_treatment",
    "ewallet",
)
ADVANCED_QUOTAS = {
    "instructions_cte_join": 2,
    "instructions_cte_window": 2,
    "instructions_date_join": 2,
    "instructions_string_matching": 1,
    "keywords_aggregate": 1,
    "keywords_ratio": 1,
}
SELECTION_RULE = (
    "all enterprise questions_gen + all enterprise instruct_basic + "
    "advanced per-db quotas selected by ascending sha256(question\\0query)"
)


class CohortError(ValueError):
    """Raised when the source snapshot cannot satisfy the frozen cohort."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise CohortError(f"cannot read {path}: {exc}") from exc


def _task(
    *,
    source_file: str,
    source_row: int,
    row: dict[str, str],
) -> dict[str, Any]:
    question = row.get("question", "")
    query = row.get("query", "")
    instructions = row.get("instructions", "")
    source_stem = Path(source_file).stem
    question_sha256 = sha256_text(question)
    return {
        "task_id": (
            f"defog-sql-eval:{source_stem}:{row.get('db_name', '')}:"
            f"{source_row}:{question_sha256[:12]}"
        ),
        "source_file": source_file,
        "source_row_0based": source_row,
        "db_name": row.get("db_name", ""),
        "query_category": row.get("query_category", ""),
        "question_sha256": question_sha256,
        "query_sha256": sha256_text(query),
        "instructions_sha256": sha256_text(instructions),
    }


def build_manifest(source_root: Path) -> dict[str, Any]:
    specifications = {
        "general": "data/questions_gen_postgres.csv",
        "basic": "data/instruct_basic_postgres.csv",
        "advanced": "data/instruct_advanced_postgres.csv",
    }
    indexed: dict[str, list[tuple[int, dict[str, str]]]] = {}
    for name, relative_path in specifications.items():
        indexed[name] = list(
            enumerate(_read_rows(source_root / relative_path))
        )

    selected: list[tuple[str, int, dict[str, str]]] = []
    for source_name in ("general", "basic"):
        relative_path = specifications[source_name]
        selected.extend(
            (relative_path, row_number, row)
            for row_number, row in indexed[source_name]
            if row.get("db_name") in ENTERPRISE_DATABASES
        )

    advanced_by_family: dict[
        tuple[str, str],
        list[tuple[int, dict[str, str]]],
    ] = defaultdict(list)
    for row_number, row in indexed["advanced"]:
        database = row.get("db_name", "")
        category = row.get("query_category", "")
        if database in ENTERPRISE_DATABASES:
            advanced_by_family[(database, category)].append((row_number, row))

    for database in ENTERPRISE_DATABASES:
        for category, quota in ADVANCED_QUOTAS.items():
            candidates = advanced_by_family[(database, category)]
            candidates.sort(
                key=lambda item: sha256_text(
                    item[1].get("question", "")
                    + "\0"
                    + item[1].get("query", "")
                )
            )
            if len(candidates) < quota:
                raise CohortError(
                    f"{database}/{category}: need {quota}, found {len(candidates)}"
                )
            selected.extend(
                (
                    specifications["advanced"],
                    row_number,
                    row,
                )
                for row_number, row in candidates[:quota]
            )

    tasks = sorted(
        (
            _task(
                source_file=source_file,
                source_row=row_number,
                row=row,
            )
            for source_file, row_number, row in selected
        ),
        key=lambda task: task["task_id"],
    )
    task_ids = [task["task_id"] for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise CohortError("generated task IDs are not unique")

    return {
        "advanced_quotas": ADVANCED_QUOTAS,
        "schema_version": SCHEMA_VERSION,
        "seed": SEED,
        "selection_rule": SELECTION_RULE,
        "tasks": tasks,
    }


def canonical_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-sha256")
    args = parser.parse_args()
    payload = canonical_bytes(build_manifest(args.source_root))
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if args.expect_sha256 and actual_sha256 != args.expect_sha256:
        raise SystemExit(
            f"manifest sha256 {actual_sha256} != expected {args.expect_sha256}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(f"wrote {args.output} ({len(payload)} bytes, sha256 {actual_sha256})")


if __name__ == "__main__":
    main()
