#!/usr/bin/env python3
"""Build an external, content-bearing candidate library for frontier replay.

The generated JSON is intentionally written outside Git. It contains source
questions and validated SQL examples, but no target-task content. The committed
experiment receipt stores only its hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from sqlglot import exp, parse_one

from defog_governed_sql_replay import GovernanceAuthority, GovernedPostgresExecutor, PinnedTaskResolver


SOURCE_FILES = frozenset({"data/instruct_basic_postgres.csv", "data/instruct_advanced_postgres.csv"})
TOKEN_RE = re.compile(r"\s+")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def surface(sql: str) -> tuple[list[str], list[str]]:
    try:
        tree = parse_one(sql, read="postgres")
    except Exception:
        return [], []
    tables = sorted({str(item.name).strip('"').lower() for item in tree.find_all(exp.Table)})
    columns = sorted({str(item.name).strip('"').lower() for item in tree.find_all(exp.Column)})
    return tables, columns


def run(*, source_root: Path, cohort_manifest: Path, dataset_manifest: Path, dsn_template: str, database: str, output: Path) -> dict[str, object]:
    resolver = PinnedTaskResolver(
        source_root=source_root,
        manifest_path=cohort_manifest,
        dataset_manifest_path=dataset_manifest,
    )
    manifest = json.loads(cohort_manifest.read_text(encoding="utf-8"))
    authority = GovernanceAuthority(
        governance_scope="enterprise",
        authorization_epoch_ref="defog-factorial-authority-v1",
        user_id="factorial-pilot-user",
        team_id="factorial-pilot-team",
        virtual_key_id="factorial-pilot-vk",
    )
    examples: list[dict[str, object]] = []
    failures: dict[str, int] = {}
    for row in manifest["tasks"]:
        if row.get("db_name") != database or row.get("source_file") not in SOURCE_FILES:
            continue
        task = resolver.resolve(row["task_id"])
        executor = GovernedPostgresExecutor(
            dsn=dsn_template.format(database=database), authority=authority, audit_path=None
        )
        try:
            executor.execute_candidate(task.gold_sql)
        except Exception as exc:
            failures[type(exc).__name__] = failures.get(type(exc).__name__, 0) + 1
            continue
        tables, columns = surface(task.gold_sql)
        normalized_sql = TOKEN_RE.sub(" ", task.gold_sql.strip())
        examples.append(
            {
                "artifact_key": "artifact-" + sha256_text(task.task_id)[:12],
                "source_question": task.question,
                "tables": tables,
                "columns": columns,
                "validated_sql": normalized_sql,
            }
        )
    if not examples:
        raise RuntimeError("no validated source examples")
    lines = [
        "COMPOSABLE VALIDATED SQL SUBPLAN LIBRARY v1",
        "This is a reference library, not an answer key. It contains only validated source examples from a separate training split.",
        "Before writing SQL: inspect the authorized schema; identify the target grain, joins, filters, grouping, ordering, and parameters.",
        "Reuse only compatible subplans or join/filter patterns. Do not copy a complete query merely because its wording is similar.",
        "Adapt identifiers and literals to the current request, execute the new candidate, repair from observed tool evidence, and submit only a successful authorized attempt.",
        "Abstain when the source examples do not provide a compatible plan.",
        "",
    ]
    for example in examples:
        lines.extend(
            [
                f"EXAMPLE {example['artifact_key']}",
                f"Source task: {example['source_question']}",
                f"Tables: {', '.join(example['tables'])}",
                f"Columns: {', '.join(example['columns'])}",
                f"Validated source SQL: {example['validated_sql']}",
                "",
            ]
        )
    candidate_text = "\n".join(lines)
    result: dict[str, object] = {
        "schema_version": "frankengate-composable-artifact-candidate-v1",
        "candidate_class": "trace2skill_style_compiled_hypothesis",
        "candidate_text": candidate_text,
        "candidate_text_sha256": sha256_text(candidate_text),
        "source_artifact_count": len(examples),
        "source_validation_failures": failures,
        "source_cohort_manifest_sha256": hashlib.sha256(cohort_manifest.read_bytes()).hexdigest(),
        "source_dataset_manifest_sha256": hashlib.sha256(dataset_manifest.read_bytes()).hexdigest(),
        "database": database,
        "promotion_authorized": False,
        "claim_boundary": "External candidate text for a small frontier replay; not a promoted skill or production artifact.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_text_sha256": result["candidate_text_sha256"], "source_artifact_count": len(examples)}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dsn-template", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(
        source_root=args.source_root.resolve(strict=True),
        cohort_manifest=args.cohort_manifest.resolve(strict=True),
        dataset_manifest=args.dataset_manifest.resolve(strict=True),
        dsn_template=args.dsn_template,
        database=args.database,
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
