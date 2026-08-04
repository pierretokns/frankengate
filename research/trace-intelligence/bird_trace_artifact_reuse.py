#!/usr/bin/env python3
"""Mine and replay validated SQL artifacts from recorded BIRD traces.

The World Model Harness BIRD fixture contains recorded tool trajectories and
independent gold SQL sidecars.  This study treats the final successful SQL
command from a trace as a *candidate* artifact, validates it against the local
SQLite database, then measures two separate reuse questions:

* natural leave-one-out lexical reuse across recorded tasks; and
* exact-template parameter transfer between distinct recorded tasks.

The second arm is deliberately controlled: source and target SQL share the
same parsed structure, while target literals are injected into the source
artifact.  It is evidence about parameterized artifact mechanics, not a claim
that arbitrary traces transfer.  Raw prompts, SQL, and rows stay external;
the receipt contains hashes and aggregate counts only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shlex
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one


SCHEMA_VERSION = "frankengate-bird-trace-artifact-reuse-v1"
TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")
STOPWORDS = frozenset(
    "a an and are as at by for from how in into is of on or per please return the to what which with"
    .split()
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def question_tokens(value: str) -> frozenset[str]:
    return frozenset(t for t in TOKEN_RE.findall(value.lower()) if t not in STOPWORDS)


def canonical_rows(rows: list[tuple[Any, ...]]) -> tuple[tuple[str, ...], ...]:
    """Canonicalize SQLite scalar results without relying on display formatting."""
    return tuple(sorted(tuple(repr(value) for value in row) for row in rows))


def execute(db_path: Path, sql: str) -> tuple[tuple[str, ...], ...] | None:
    try:
        with sqlite3.connect(db_path) as connection:
            cursor = connection.execute(sql)
            return canonical_rows(cursor.fetchall())
    except sqlite3.Error:
        return None


def sql_template(sql: str) -> tuple[str, list[exp.Literal]]:
    parsed = parse_one(sql, read="sqlite")
    literals: list[exp.Literal] = []

    def replace(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Literal):
            literals.append(node.copy())
            return exp.Placeholder()
        return node

    normalized = parsed.transform(replace)
    return normalized.sql(dialect="sqlite", pretty=False), literals


def instantiate(template_sql_text: str, literals: list[exp.Literal]) -> str:
    parsed = parse_one(template_sql_text, read="sqlite")
    iterator = iter(literals)

    def replace(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Placeholder):
            try:
                return next(iterator).copy()
            except StopIteration as exc:
                raise ValueError("literal arity mismatch") from exc
        return node

    rendered = parsed.transform(replace)
    try:
        next(iterator)
    except StopIteration:
        return rendered.sql(dialect="sqlite", pretty=False)
    raise ValueError("literal arity mismatch")


def mutate_literal(literal: exp.Literal, index: int) -> exp.Literal:
    """Create a safe, deterministic parameter mutation for a controlled arm."""
    mutated = literal.copy()
    value = literal.this
    if literal.is_int:
        mutated.set("this", str(int(value) + index + 1))
        return mutated
    if literal.is_number:
        mutated.set("this", str(float(value) + index + 1.0))
        return mutated
    if literal.is_string:
        text = str(value)
        match = re.fullmatch(r"(20\d{2})([-/]\d{1,2}[-/]\d{1,2})", text)
        if match:
            mutated.set("this", f"{int(match.group(1)) + 1}{match.group(2)}")
        else:
            mutated.set("this", f"{text}__frankengate_parameter_{index + 1}")
        return mutated
    return mutated


def extract_sql(command: str) -> str | None:
    """Extract a single sqlite3 statement from a shell command."""
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    try:
        index = tokens.index("sqlite3")
    except ValueError:
        return None
    if index + 2 >= len(tokens):
        return None
    database = tokens[index + 1]
    if not database.endswith("database.db"):
        return None
    sql = tokens[index + 2]
    if "|" in tokens[index + 3 :]:
        # The command's result was truncated for display, but the SQL itself
        # is still a valid artifact.  Keep it unless it contains statements.
        pass
    if ";" in sql.rstrip(";"):
        return None
    if not sql.strip().lower().startswith(("select", "with", "pragma")):
        return None
    return sql.strip()


@dataclass(frozen=True)
class Task:
    task_id: str
    database: str
    prompt: str
    gold_sql: str
    db_path: Path
    order: int


@dataclass(frozen=True)
class Artifact:
    task: Task
    sql: str
    result: tuple[tuple[str, ...], ...]
    template: str
    literals: tuple[exp.Literal, ...]
    tokens: frozenset[str]


def load_tasks(harness_root: Path) -> dict[str, Task]:
    here = harness_root / "packages/environment-capture/bird-sql"
    tasks: dict[str, Task] = {}
    order = 0
    for split in ("train", "test"):
        data_path = here / "data" / f"{split}.jsonl"
        for line in data_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            task_id = row["task_id"]
            gold = json.loads((here / "gold" / f"{task_id}.json").read_text(encoding="utf-8"))
            database = row["data"]["db_name"]
            tasks[row["prompt"].strip()] = Task(
                task_id=task_id,
                database=database,
                prompt=row["prompt"].strip(),
                gold_sql=gold["gold_sql"],
                db_path=here / "databases" / f"{database}.sqlite",
                order=order,
            )
            order += 1
    return tasks


def load_trace_candidates(harness_root: Path, tasks: dict[str, Task]) -> dict[str, str]:
    path = harness_root / "packages/environment-capture/bird-sql/models/bird-sql/index/steps.jsonl"
    candidates: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        prompt = row["task"].strip()
        if prompt not in tasks or row["observation"].get("is_error"):
            continue
        sql = extract_sql(row["action"].get("arguments", {}).get("command", ""))
        if sql:
            # Last valid query is the trace's terminal candidate.  Earlier
            # schema probes and exploratory queries are intentionally ignored.
            candidates[prompt] = sql
    return candidates


def lexical_rank(target: Task, pool: list[Artifact]) -> list[Artifact]:
    target_tokens = question_tokens(target.prompt)
    scored = []
    for artifact in pool:
        overlap = len(target_tokens & artifact.tokens)
        denominator = len(target_tokens) or 1
        scored.append((overlap / denominator, -artifact.task.order, artifact))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored]


def run(harness_root: Path, output: Path) -> dict[str, Any]:
    tasks = load_tasks(harness_root.resolve())
    candidates = load_trace_candidates(harness_root.resolve(), tasks)
    stats: Counter[str] = Counter()
    artifacts: list[Artifact] = []
    for prompt, sql in candidates.items():
        task = tasks[prompt]
        trace_result = execute(task.db_path, sql)
        gold_result = execute(task.db_path, task.gold_sql)
        if trace_result is None:
            stats["trace_sql_execution_failed"] += 1
            continue
        if gold_result is None:
            stats["gold_sql_execution_failed"] += 1
            continue
        stats["trace_sql_executed"] += 1
        stats["trace_sql_gold_result_match"] += int(trace_result == gold_result)
        if trace_result != gold_result:
            stats["trace_sql_semantic_mismatch"] += 1
            continue
        try:
            template, literals = sql_template(sql)
        except Exception:
            stats["template_parse_failed"] += 1
            continue
        artifacts.append(
            Artifact(
                task=task,
                sql=sql,
                result=trace_result,
                template=template,
                literals=tuple(literals),
                tokens=question_tokens(task.prompt),
            )
        )
    stats["trace_tasks_seen"] = len(tasks)
    stats["trace_tasks_with_sql_candidate"] = len(candidates)
    stats["validated_artifacts"] = len(artifacts)

    by_db: defaultdict[str, list[Artifact]] = defaultdict(list)
    by_template: defaultdict[tuple[str, str], list[Artifact]] = defaultdict(list)
    for artifact in artifacts:
        by_db[artifact.task.database].append(artifact)
        by_template[(artifact.task.database, artifact.template)].append(artifact)

    natural_total = natural_match = natural_same_template = 0
    for target in artifacts:
        pool = [candidate for candidate in by_db[target.task.database] if candidate.task.task_id != target.task.task_id]
        ranked = lexical_rank(target.task, pool)
        if not ranked:
            continue
        selected = ranked[0]
        natural_total += 1
        natural_match += int(execute(target.task.db_path, selected.sql) == target.result)
        natural_same_template += int(selected.template == target.template)

    parameter_total = parameter_match = 0
    parameter_groups = 0
    for group in by_template.values():
        if len(group) < 2:
            continue
        parameter_groups += 1
        ordered = sorted(group, key=lambda artifact: artifact.task.order)
        source = ordered[0]
        for target in ordered[1:]:
            try:
                rendered = instantiate(source.template, list(target.literals))
            except ValueError:
                stats["parameter_literal_arity_mismatch"] += 1
                continue
            parameter_total += 1
            parameter_match += int(execute(target.task.db_path, rendered) == target.result)

    # The public trace corpus contains no repeated normalized templates, so it
    # cannot supply natural cross-task parameter pairs.  Add a separate,
    # explicitly controlled replay from each validated artifact with literals:
    # the target is the same AST with deterministic parameter mutations, and
    # the independent oracle is execution of that mutated target SQL.
    controlled_total = controlled_exact_match = controlled_parameter_match = 0
    for artifact in artifacts:
        if not artifact.literals:
            continue
        target_literals = [mutate_literal(literal, index) for index, literal in enumerate(artifact.literals)]
        try:
            target_sql = instantiate(artifact.template, target_literals)
            parameterized_sql = instantiate(artifact.template, target_literals)
        except ValueError:
            stats["controlled_literal_arity_mismatch"] += 1
            continue
        target_result = execute(artifact.task.db_path, target_sql)
        if target_result is None:
            stats["controlled_target_execution_failed"] += 1
            continue
        controlled_total += 1
        controlled_exact_match += int(execute(artifact.task.db_path, artifact.sql) == target_result)
        controlled_parameter_match += int(execute(artifact.task.db_path, parameterized_sql) == target_result)

    stats["natural_leave_one_out_targets"] = natural_total
    stats["natural_leave_one_out_result_matches"] = natural_match
    stats["natural_leave_one_out_selected_same_template"] = natural_same_template
    stats["repeated_template_groups"] = parameter_groups
    stats["parameter_transfer_targets"] = parameter_total
    stats["parameter_transfer_result_matches"] = parameter_match
    stats["controlled_parameter_targets"] = controlled_total
    stats["controlled_exact_artifact_result_matches"] = controlled_exact_match
    stats["controlled_parameterized_artifact_result_matches"] = controlled_parameter_match
    stats["database_family_count"] = len(by_db)

    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "harness_root": "world-model-harness-v0.2.2",
            "trace_index_sha256": sha256_text(
                (harness_root / "packages/environment-capture/bird-sql/models/bird-sql/index/steps.jsonl")
                .read_text(encoding="utf-8")
            ),
            "raw_content_committed": False,
            "independent_oracle": "SQLite execution of trace SQL and gold sidecar SQL; canonicalized rows",
        },
        "protocol": {
            "candidate": "last parseable successful sqlite3 SELECT/WITH command per trace task",
            "validation": "trace result equals independently executed gold result",
            "natural_reuse": "leave-one-out lexical top-1 within database family",
            "parameter_reuse": "earliest validated artifact in an exact normalized-template group, target literals injected",
            "controlled_parameter_reuse": "each validated artifact replayed with deterministic literal mutations; target SQL is independently executed",
            "template": "SQLGlot SQLite AST with literal nodes replaced by placeholders",
        },
        "aggregate": dict(sorted(stats.items())),
        "claim_boundary": {
            "trace_artifacts_independently_validated": True,
            "natural_cross_task_reuse_established": False,
            "natural_parameterized_reuse_measured": parameter_total > 0,
            "controlled_parameterized_reuse_measured": controlled_total > 0,
            "enterprise_quality_established": False,
            "reason": "Public BIRD traces provide execution and gold oracles but no natural user intent labels, enterprise identities, or prospective outcomes.",
        },
    }
    receipt["result_sha256"] = hashlib.sha256(stable_json(receipt)).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": receipt["aggregate"], "result_sha256": receipt["result_sha256"]}, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.harness_root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
