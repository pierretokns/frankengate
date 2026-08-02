#!/usr/bin/env python3
"""Run a content-free ontology/action projection probe on WMH-BIRD traces.

This is the first executable slice of the ontology/action protocol.  It does
not claim that table names are a corporate ontology: WMH-BIRD provides SQL
table references and SQLite replay outcomes, but no reviewed aliases,
principals, authority epochs, or human intent labels.  The receipt therefore
reports exact-table and replay-compatible retrieval only, and explicitly marks
the semantic/authority arms that this proxy cannot identify.

The runnable arms are deliberately deterministic:

* A0 lexical table retrieval;
* A1 typed schema projection (table + column identifiers);
* A2 provenance/alias edge projection learned from the training fold;
* A3 typed + provenance + lexical retrieval;
* A6 replay-backed action evidence projected from successful training traces;
* A7 schema-first bootstrap (the same typed projection, named separately for
  the protocol matrix).

A4 (vector), A5 (authority-constrained graph), and A8 (frontier refinement)
are recorded as unavailable unless their required external evidence is
provided.  No raw prompts, SQL, or schema text are written to the receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from modern_term_acronym_port import STOP, stable_hash, tokens
from wmh_bird_exposure_counterfactual import Trace, execute, file_hash, load_traces
from wmh_bird_equivalence_aware_retrieval import equivalent_candidates


SCHEMA_VERSION = "frankengate-ontology-action-trace-projection-cohort-v1"


def rank_metrics(order: list[str], targets: set[str], compatible: set[str]) -> dict[str, float]:
    exact_positions = [index for index, item in enumerate(order, 1) if item in targets]
    compatible_positions = [index for index, item in enumerate(order, 1) if item in compatible]
    first = exact_positions[0] if exact_positions else None
    compatible_first = compatible_positions[0] if compatible_positions else None
    return {
        "strict_mrr": round(1.0 / first, 6) if first else 0.0,
        "strict_recall_at_1": float(first == 1),
        "strict_recall_at_3": float(first is not None and first <= 3),
        "strict_recall_at_10": float(first is not None and first <= 10),
        "compatible_mrr": round(1.0 / compatible_first, 6) if compatible_first else 0.0,
        "compatible_recall_at_1": float(compatible_first == 1),
        "compatible_recall_at_3": float(compatible_first is not None and compatible_first <= 3),
        "compatible_recall_at_10": float(compatible_first is not None and compatible_first <= 10),
    }


def aggregate(rows: list[dict[str, float]]) -> dict[str, Any]:
    if not rows:
        return {"cases": 0}
    keys = (
        "strict_mrr",
        "strict_recall_at_1",
        "strict_recall_at_3",
        "strict_recall_at_10",
        "compatible_mrr",
        "compatible_recall_at_1",
        "compatible_recall_at_3",
        "compatible_recall_at_10",
    )
    return {"cases": len(rows), **{key: round(sum(row[key] for row in rows) / len(rows), 6) for key in keys}}


def normalize_terms(value: str) -> set[str]:
    return {item for item in tokens(value.replace("_", " ")) if item not in STOP}


def lexical_score(prompt: str, table: str) -> float:
    query = normalize_terms(prompt)
    candidate = normalize_terms(table)
    exact = 10.0 if table.casefold() in query else 0.0
    return exact + float(len(query & candidate))


def ngrams(prompt: str, max_n: int = 4) -> dict[str, str]:
    words = [word for word in tokens(prompt) if word not in STOP]
    output: dict[str, str] = {}
    for size in range(1, max_n + 1):
        for index in range(len(words) - size + 1):
            phrase = " ".join(words[index : index + size])
            output[stable_hash(phrase)] = phrase
    return output


def schema_terms(db_root: Path, db_name: str, table: str) -> set[str]:
    """Read only typed identifiers from the pinned SQLite schema."""
    path = db_root / db_name / f"{db_name}.sqlite"
    try:
        with sqlite3.connect(path) as connection:
            columns = [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')]
    except sqlite3.Error:
        columns = []
    return normalize_terms(table) | {term for column in columns for term in normalize_terms(column)}


def recorded_schema_terms(traces_path: Path) -> dict[str, dict[str, set[str]]]:
    """Extract only table/column identifiers present in recorded tool DDL."""
    create_block = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?"
        r"([A-Za-z_][A-Za-z0-9_]*)[\"`\]]?\s*\((.*?)\)\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    column_line = re.compile(r"^\s*[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)[\"`\]]?\s+", re.MULTILINE)
    output: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for line in traces_path.open(encoding="utf-8", errors="replace"):
        try:
            span = json.loads(line)
        except json.JSONDecodeError:
            continue
        trace_id = span.get("traceId")
        if not isinstance(trace_id, str):
            continue
        trace_hash = hashlib.sha256(trace_id.encode()).hexdigest()
        for item in span.get("attributes", []):
            if not isinstance(item, dict) or item.get("key") != "gen_ai.tool.message":
                continue
            value = item.get("value")
            if not isinstance(value, dict) or not isinstance(value.get("stringValue"), str):
                continue
            for match in create_block.finditer(value["stringValue"]):
                table = match.group(1).casefold()
                terms = output[trace_hash][table]
                terms.update(normalize_terms(table))
                for column in column_line.findall(match.group(2)):
                    if column.casefold() not in {"primary", "foreign", "unique", "constraint", "check"}:
                        terms.update(normalize_terms(column))
    return {trace_hash: dict(tables) for trace_hash, tables in output.items()}


def typed_score(prompt: str, db_root: Path, db_name: str, table: str, terms_override: set[str] | None = None) -> float:
    query = normalize_terms(prompt)
    terms = terms_override if terms_override is not None else schema_terms(db_root, db_name, table)
    return lexical_score(prompt, table) + 2.0 * len(query & terms - normalize_terms(table))


def split_by_db(traces: Iterable[Trace]) -> tuple[list[Trace], list[Trace]]:
    grouped: dict[str, list[Trace]] = defaultdict(list)
    for trace in traces:
        grouped[trace.db_name].append(trace)
    train: list[Trace] = []
    evaluation: list[Trace] = []
    for db_name in sorted(grouped):
        ordered = sorted(grouped[db_name], key=lambda item: stable_hash(item.base_task_id))
        train.extend(ordered[::2])
        evaluation.extend(ordered[1::2])
    return train, evaluation


def build_alias_edges(train: Iterable[Trace], *, replay_only: bool = False, db_root: Path | None = None) -> dict[tuple[str, str], set[str]]:
    edges: dict[tuple[str, str], set[str]] = defaultdict(set)
    for trace in train:
        if replay_only:
            if db_root is None:
                raise ValueError("db_root is required for replay-backed edges")
            status, _ = execute(db_root / trace.db_name / f"{trace.db_name}.sqlite", trace.sql)
            if status != "ok":
                continue
        for term_hash in ngrams(trace.prompt):
            for table in trace.used_tables & trace.exposed_tables:
                edges[(trace.db_name, term_hash)].add(table)
    return edges


def rank_arm(
    arm: str,
    trace: Trace,
    candidates: list[str],
    db_root: Path,
    alias_edges: dict[tuple[str, str], set[str]],
    action_edges: dict[tuple[str, str], set[str]],
    schema_terms_by_trace: dict[str, dict[str, set[str]]] | None = None,
) -> list[str]:
    prompt_terms = ngrams(trace.prompt)
    aliases = set().union(*(alias_edges.get((trace.db_name, key), set()) for key in prompt_terms))
    actions = set().union(*(action_edges.get((trace.db_name, key), set()) for key in prompt_terms))
    trace_schema = (schema_terms_by_trace or {}).get(trace.trace_hash, {})

    if arm == "A0":
        return sorted(candidates, key=lambda item: (-lexical_score(trace.prompt, item), item))
    if arm in {"A1", "A7"}:
        return sorted(candidates, key=lambda item: (-typed_score(trace.prompt, db_root, trace.db_name, item, trace_schema.get(item.casefold())), item))
    if arm == "A2":
        return sorted(candidates, key=lambda item: (-lexical_score(trace.prompt, item) - (20.0 if item in aliases else 0.0), item))
    if arm == "A3":
        return sorted(candidates, key=lambda item: (-typed_score(trace.prompt, db_root, trace.db_name, item, trace_schema.get(item.casefold())) - (20.0 if item in aliases else 0.0), item))
    if arm == "A6":
        return sorted(candidates, key=lambda item: (-typed_score(trace.prompt, db_root, trace.db_name, item, trace_schema.get(item.casefold())) - (20.0 if item in actions else 0.0), item))
    raise ValueError(f"unsupported runnable arm: {arm}")


def object_edge_counts(traces: list[Trace], schema_terms_by_trace: dict[str, dict[str, set[str]]]) -> dict[str, Any]:
    objects: defaultdict[str, set[str]] = defaultdict(set)
    edges: defaultdict[str, int] = defaultdict(int)
    for trace in traces:
        task_id = hashlib.sha256(trace.base_task_id.encode()).hexdigest()
        trace_id = trace.trace_hash
        system_id = stable_hash(f"system:{trace.db_name}")
        objects["task"].add(task_id)
        objects["trace"].add(trace_id)
        objects["system"].add(system_id)
        objects["artifact"].add(stable_hash(f"sql:{trace.sql}"))
        objects["action"].add(stable_hash(f"replay:{trace.trace_hash}"))
        objects["outcome"].add(stable_hash(f"outcome:{trace.trace_hash}"))
        edges["task_contains_trace"] += 1
        edges["trace_uses_system"] += 1
        edges["trace_exposes_schema"] += len(trace.exposed_tables)
        edges["trace_uses_artifact"] += len(trace.used_tables)
        edges["action_targets_artifact"] += 1
        edges["action_has_outcome"] += 1
        for table in trace.exposed_tables:
            objects["schema"].add(stable_hash(f"schema:{trace.db_name}:{table}"))
            # Columns are not stored in the receipt; only a stable object count
            # is emitted from DDL present in the recorded tool message.
            for _ in schema_terms_by_trace.get(trace.trace_hash, {}).get(table, set()) - normalize_terms(table):
                objects["schema_column"].add(stable_hash(f"column:{trace.db_name}:{table}:{_}"))
    return {"objects": {key: len(value) for key, value in sorted(objects.items())}, "edges": dict(sorted(edges.items()))}


def run(traces_path: Path, manifest: Path, db_root: Path, output: Path) -> dict[str, Any]:
    traces = load_traces(traces_path, manifest)
    train, evaluation = split_by_db(traces)
    schema_terms_by_trace = recorded_schema_terms(traces_path)
    alias_edges = build_alias_edges(train)
    action_edges = build_alias_edges(train, replay_only=True, db_root=db_root)
    arms = ("A0", "A1", "A2", "A3", "A6", "A7")
    metrics: dict[str, list[dict[str, float]]] = defaultdict(list)
    for trace in evaluation:
        candidates = sorted(trace.exposed_tables)
        exact = set(trace.used_tables & trace.exposed_tables)
        equivalents, _, _ = equivalent_candidates(trace, db_root)
        compatible = exact | equivalents
        for arm in arms:
            order = rank_arm(arm, trace, candidates, db_root, alias_edges, action_edges, schema_terms_by_trace)
            metrics[arm].append(rank_metrics(order, exact, compatible))

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "traces_sha256": file_hash(traces_path),
            "manifest_sha256": file_hash(manifest),
            "raw_content_committed": False,
            "sqlite_root": "external-pinned-bird-minidev",
        },
        "cohort": {
            "selected_successful_tasks": len(traces),
            "train_tasks": len(train),
            "evaluation_tasks": len(evaluation),
            "database_families": len({trace.db_name for trace in traces}),
            "split": "within-database deterministic even/odd task split",
            "candidate_pool": "exposed schema tables per trace",
            "typed_identifiers": "table and column names parsed from recorded gen_ai.tool.message DDL",
            "strict_target": "recorded SQL table references",
            "compatible_target": "recorded references plus SQLite result-preserving substitutions",
        },
        "projection": object_edge_counts(traces, schema_terms_by_trace),
        "arms": {arm: {"status": "measured", "metrics": aggregate(rows)} for arm, rows in sorted(metrics.items())},
        "unmeasured_arms": {
            "A4": {"status": "unavailable", "reason": "no embedding endpoint supplied; no dense claim"},
            "A5": {"status": "unidentifiable", "reason": "proxy has no principal, policy epoch, or authority labels"},
            "A8": {"status": "unavailable", "reason": "no independent frontier adjudication fixture supplied"},
        },
        "action_states": {
            "proposed": len(evaluation),
            "approved": len(train),
            "replayed": len(traces),
            "promoted": 0,
            "rejected": 0,
            "deprecated": 0,
        },
        "claim_boundary": {
            "schema_first_projection_measured": True,
            "typed_identifier_retrieval_measured": True,
            "replay_compatible_retrieval_measured": True,
            "corporate_alias_quality_established": False,
            "ontology_quality_established": False,
            "authority_safety_established": False,
            "semantic_execution_success_established": False,
            "skill_transfer_established": False,
            "reason": "WMH-BIRD supplies SQL table references and SQLite outcomes, but no reviewed enterprise ontology, principal scopes, authority epochs, or human intent labels.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cohort": result["cohort"], "arms": result["arms"], "unmeasured_arms": result["unmeasured_arms"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
