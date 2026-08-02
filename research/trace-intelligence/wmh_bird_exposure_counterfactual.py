#!/usr/bin/env python3
"""Turn exposed WMH-BIRD schema tables into replay-checked SQL negatives.

An exposed-but-unused table is not automatically a semantic negative: an agent
may omit a valid table for cost, authority, or query-shape reasons.  This
experiment therefore creates a narrower, outcome-backed label.  For each
recorded successful trace, one exposed table is substituted for one table used
by the recorded SQL and the result is independently replayed on the pinned
SQLite archive.  Execution errors and result mismatches are
*counterfactual-interchangeability negatives*, not claims of human intent.

The same receipt also measures the Termolator/TermSuite-style port as a
search-only alias feature over the exposed table pool.  It never writes an
ontology, memory, embedding, or skill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one

from modern_term_acronym_port import STOP, stable_hash, termhood, tokens


SCHEMA_VERSION = "frankengate-wmh-bird-exposure-counterfactual-v1"
CREATE_TABLE = re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)", re.I)
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


@dataclass(frozen=True)
class Trace:
    trace_hash: str
    base_task_id: str
    db_name: str
    prompt: str
    sql: str
    reward: float
    exposed_tables: frozenset[str]
    used_tables: frozenset[str]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def attrs(span: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in span.get("attributes", []):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        value = item.get("value")
        if not isinstance(value, dict):
            continue
        for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if key in value:
                values[item["key"]] = value[key]
                break
    return values


def sql_tables(sql: str) -> frozenset[str]:
    try:
        return frozenset(table.name.casefold() for table in parse_one(sql, read="sqlite").find_all(exp.Table))
    except Exception:
        values: set[str] = set()
        for match in re.finditer(r"\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.I):
            values.add(match.group(1).casefold())
        return frozenset(values)


def load_db_map(manifest: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in manifest.open(encoding="utf-8"):
        row = json.loads(line)
        mapping[str(row["task_id"])] = str(row["data"]["db_name"])
    return mapping


def load_traces(path: Path, manifest: Path) -> list[Trace]:
    db_map = load_db_map(manifest)
    grouped: dict[str, dict[str, Any]] = {}
    for line in path.open(encoding="utf-8", errors="replace"):
        span = json.loads(line)
        trace_id = span.get("traceId")
        if not isinstance(trace_id, str):
            continue
        record = grouped.setdefault(trace_id, {"schema": set()})
        values = attrs(span)
        for key, value in values.items():
            if value is not None and key != "gen_ai.tool.message":
                record[key] = value
        message = values.get("gen_ai.tool.message")
        if isinstance(message, str):
            record["schema"].update(item.casefold() for item in CREATE_TABLE.findall(message))

    by_task: dict[str, list[Trace]] = defaultdict(list)
    for trace_id, record in grouped.items():
        raw_metadata = record.get("wmh.trace.metadata")
        if not isinstance(raw_metadata, str):
            continue
        try:
            metadata = json.loads(raw_metadata)
        except json.JSONDecodeError:
            continue
        if not isinstance(metadata, dict):
            continue
        base = str(metadata.get("base_task_id", ""))
        sql = str(metadata.get("final_answer", ""))
        prompt = str(record.get("gen_ai.prompt", ""))
        if not base or not sql or not prompt or base not in db_map:
            continue
        try:
            reward = float(metadata.get("reward", 0.0))
        except (TypeError, ValueError):
            reward = 0.0
        used = sql_tables(sql)
        exposed = frozenset(record["schema"])
        if not used or not exposed:
            continue
        by_task[base].append(Trace(
            trace_hash=hashlib.sha256(trace_id.encode()).hexdigest(),
            base_task_id=base,
            db_name=db_map[base],
            prompt=prompt,
            sql=sql,
            reward=reward,
            exposed_tables=exposed,
            used_tables=used,
        ))

    # One deterministic successful trace per task prevents the 22 repeated
    # model runs from pretending to be independent task labels.
    selected: list[Trace] = []
    for base in sorted(by_task):
        successful = [row for row in by_task[base] if row.reward == 1.0]
        if successful:
            selected.append(sorted(successful, key=lambda row: row.trace_hash)[0])
    return selected


def substitute_table(sql: str, old: str, new: str) -> str:
    tree = parse_one(sql, read="sqlite")
    for table in tree.find_all(exp.Table):
        if table.name.casefold() == old.casefold():
            table.set("this", exp.Identifier(this=new, quoted=False))
    return tree.sql(dialect="sqlite")


def execute(path: Path, sql: str) -> tuple[str, list[tuple[Any, ...]] | None]:
    try:
        with sqlite3.connect(path) as connection:
            rows = connection.execute(sql).fetchall()
        return "ok", rows
    except (sqlite3.Error, ValueError):
        return "error", None


def table_tokens(name: str) -> set[str]:
    return {item for item in tokens(name.replace("_", " ")) if item not in STOP}


def lexical_score(prompt: str, table: str) -> float:
    query = set(tokens(prompt)) - STOP
    terms = table_tokens(table)
    exact = 10.0 if table.casefold() in query else 0.0
    return exact + float(len(query & terms))


def ngrams(prompt: str, max_n: int = 4) -> dict[str, str]:
    words = [word for word in tokens(prompt) if word not in STOP]
    output: dict[str, str] = {}
    for n in range(1, max_n + 1):
        for index in range(len(words) - n + 1):
            phrase = " ".join(words[index : index + n])
            output[stable_hash(phrase)] = phrase
    return output


def aggregate_ranks(rows: list[dict[str, float]]) -> dict[str, Any]:
    if not rows:
        return {"cases": 0, "mrr": 0.0, "recall_at_1": 0.0, "recall_at_5": 0.0, "recall_at_10": 0.0}
    return {
        "cases": len(rows),
        "mrr": round(sum(row["mrr"] for row in rows) / len(rows), 6),
        "recall_at_1": round(sum(row["recall_at_1"] for row in rows) / len(rows), 6),
        "recall_at_5": round(sum(row["recall_at_5"] for row in rows) / len(rows), 6),
        "recall_at_10": round(sum(row["recall_at_10"] for row in rows) / len(rows), 6),
    }


def rank_metrics(order: list[str], targets: frozenset[str]) -> dict[str, float]:
    positions = [index for index, item in enumerate(order, 1) if item in targets]
    first = positions[0] if positions else None
    return {
        "mrr": 1.0 / first if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "recall_at_10": float(first is not None and first <= 10),
    }


def run(traces: Path, manifest: Path, db_root: Path, output: Path, limit: int = 3000) -> dict[str, Any]:
    selected = load_traces(traces, manifest)
    replay_counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    by_db: dict[str, list[Trace]] = defaultdict(list)
    for trace in selected:
        db_path = db_root / trace.db_name / f"{trace.db_name}.sqlite"
        base_status, base_rows = execute(db_path, trace.sql)
        replay_counts[f"base_{base_status}"] += 1
        pair_counts: Counter[str] = Counter()
        candidate_tables = trace.exposed_tables - trace.used_tables
        if base_status == "ok":
            for old in sorted(trace.used_tables):
                for candidate in sorted(candidate_tables):
                    try:
                        counterfactual = substitute_table(trace.sql, old, candidate)
                    except Exception:
                        pair_counts["counterfactual_error"] += 1
                        continue
                    status, result = execute(db_path, counterfactual)
                    if status != "ok":
                        pair_counts["counterfactual_error"] += 1
                    elif result == base_rows:
                        pair_counts["counterfactual_match"] += 1
                    else:
                        pair_counts["counterfactual_mismatch"] += 1
        rows.append({
            "trace_hash": trace.trace_hash,
            "db_name": trace.db_name,
            "base_replay": base_status,
            "exposed_tables": len(trace.exposed_tables),
            "used_tables": len(trace.used_tables),
            "candidate_tables": len(candidate_tables),
            **dict(pair_counts),
        })
        if base_status == "ok" and trace.used_tables & trace.exposed_tables:
            by_db[trace.db_name].append(trace)

    retrieval_rows: dict[str, list[dict[str, float]]] = defaultdict(list)
    fold_summaries: list[dict[str, Any]] = []
    for db in sorted(by_db):
        ordered = sorted(by_db[db], key=lambda row: stable_hash(row.base_task_id))
        train, evaluation = ordered[::2], ordered[1::2]
        foreground = [row.prompt for row in train]
        candidates = termhood(foreground, foreground, limit=limit)
        admitted = {row["term_hash"] for row in candidates}
        mapping: dict[tuple[str, str], set[str]] = defaultdict(set)
        for row in train:
            for term_hash in ngrams(row.prompt):
                if term_hash in admitted:
                    for table in row.used_tables & row.exposed_tables:
                        mapping[(db, term_hash)].add(table)
        for row in evaluation:
            pool = sorted(row.exposed_tables)
            targets = row.used_tables & row.exposed_tables
            if not pool or not targets:
                continue
            terms = ngrams(row.prompt)
            aliases = set().union(*(mapping.get((db, key), set()) for key in terms)) if terms else set()
            lexical = sorted(pool, key=lambda table: (-lexical_score(row.prompt, table), table))
            enriched = sorted(pool, key=lambda table: (-lexical_score(row.prompt, table) - (20.0 if table in aliases else 0.0), table))
            retrieval_rows["lexical"].append(rank_metrics(lexical, frozenset(targets)))
            retrieval_rows["lexical_plus_termhood_alias"].append(rank_metrics(enriched, frozenset(targets)))
        fold_summaries.append({"db_name": db, "train_tasks": len(train), "evaluation_tasks": len(evaluation), "term_candidate_count": len(candidates), "mapped_term_count": len(mapping)})

    aggregate = {
        "selected_successful_tasks": len(selected),
        "database_families": len(by_db),
        "base_replay_counts": dict(sorted(replay_counts.items())),
        "counterfactual_pairs": sum(int(row.get("counterfactual_error", 0)) + int(row.get("counterfactual_match", 0)) + int(row.get("counterfactual_mismatch", 0)) for row in rows),
        "counterfactual_execution_errors": sum(int(row.get("counterfactual_error", 0)) for row in rows),
        "counterfactual_result_mismatches": sum(int(row.get("counterfactual_mismatch", 0)) for row in rows),
        "counterfactual_result_matches": sum(int(row.get("counterfactual_match", 0)) for row in rows),
    }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"traces_sha256": file_hash(traces), "manifest_sha256": file_hash(manifest), "raw_content_committed": False, "sqlite_root": "external-pinned-bird-minidev"},
        "cohort": {"selection": "one deterministic reward=1 trace per base task", "task_count": len(selected), "database_families": len(by_db), "candidate_pool": "schema tables exposed by the trace", "counterfactual": "replace each used table with each exposed-but-unused table and replay on SQLite"},
        "aggregate": aggregate,
        "retrieval": {"folds": fold_summaries, "arms": {arm: aggregate_ranks(values) for arm, values in sorted(retrieval_rows.items())}},
        "rows": rows,
        "claim_boundary": {"counterfactual_interchangeability_negatives_measured": True, "semantic_negative_labels_established": False, "enterprise_alias_quality_established": False, "validated_artifact_utility_measured": False, "reason": "Replay failures and result mismatches show that exposed tables are not interchangeable with the recorded table under this SQL. They do not prove that a table is semantically irrelevant to the user's intent."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": aggregate, "retrieval": result["retrieval"]["arms"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3000)
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
