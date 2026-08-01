#!/usr/bin/env python3
"""Stress same-scope schema collisions on the frozen real NL2SQL cohort.

The earlier real-alias benchmark measured target retrieval against a broad set
of all gold-referenced objects. That makes ``sales.id`` and
``salespersons.id`` simultaneously relevant and cannot expose a same-scope
collision. This benchmark chooses one deterministic focus object per question
from the gold-referenced objects that have a same-normalized-name sibling in a
different table of the same database. The focus object is a *gold-SQL proxy*,
not semantic-alias ground truth.

Raw questions/SQL and candidate names remain external. The output uses the
same content-free receipt shape as the real-alias benchmark so its verifier can
check candidate/order/metric hashes independently.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from nl2sql_real_alias_benchmark import (
    EMBED_MODEL,
    DEFAULT_MODEL,
    _aggregate,
    _call_frontier,
    _order_from_scores,
    _prompt,
    candidate_fingerprint,
    candidate_key,
    cosine,
    exact_surface,
    file_sha256,
    post_embed,
    stable_hash,
)
from nl2sql_real_alias_cohort import lexical_score, normalize, schema_from_ddl


SCHEMA_VERSION = "frankengate-nl2sql-same-scope-collision-benchmark-v1"
DATABASES = ("broker", "car_dealership", "derm_treatment", "ewallet")


def _candidate(db: str, table: str, identifier: str) -> dict[str, str]:
    return {"db": db, "table": table, "identifier": identifier}


def _schema_candidates(db: str, schema: dict[str, list[str]]) -> list[dict[str, str]]:
    return [_candidate(db, table, identifier) for table, columns in schema.items() for identifier in [table, *columns]]


def build_cases(raw_path: Path, ddl_root: Path, output_raw: Path, *, limit: int | None = None) -> dict[str, Any]:
    source = json.loads(raw_path.read_text(encoding="utf-8"))
    schemas = {db: schema_from_ddl(ddl_root / db / f"{db}.sql") for db in DATABASES}
    cases: list[dict[str, Any]] = []
    for original in sorted(source["cases"], key=lambda case: case["case_id"]):
        if not original.get("target_objects"):
            continue
        db = str(original["scope_db"])
        all_schema = _schema_candidates(db, schemas[db])
        options: list[tuple[float, dict[str, str], list[dict[str, str]]]] = []
        for target in original["target_objects"]:
            target_key = (target["table"], target["identifier"])
            collisions = [
                candidate for candidate in all_schema
                if normalize(candidate["identifier"]) == normalize(target["identifier"])
                and (candidate["table"], candidate["identifier"]) != target_key
            ]
            if collisions:
                options.append((lexical_score(original["question"], target), {"db": db, "table": target["table"], "identifier": target["identifier"]}, collisions))
        if not options:
            continue
        _, focus, collisions = max(options, key=lambda item: (item[0], item[1]["table"], item[1]["identifier"]))
        pool: dict[tuple[str, str, str], dict[str, str]] = {}
        required = [focus, *collisions]
        for candidate in required:
            pool[candidate_key(candidate)] = candidate
        for candidate in sorted(original["candidates"], key=lambda item: (-lexical_score(original["question"], item), item["db"], item["table"], item["identifier"])):
            pool[candidate_key(candidate)] = candidate
        ranked_schema = sorted(all_schema, key=lambda item: (-lexical_score(original["question"], item), item["table"], item["identifier"]))
        for candidate in ranked_schema:
            pool[candidate_key(candidate)] = candidate
        ordered = sorted(pool.values(), key=lambda item: (item["db"] != db, -lexical_score(original["question"], item), item["table"], item["identifier"]))
        candidates: list[dict[str, str]] = []
        for candidate in [*required, *ordered]:
            if candidate_key(candidate) not in {candidate_key(item) for item in candidates}:
                candidates.append(candidate)
            if len(candidates) >= 24:
                break
        cases.append({
            "case_id": f"collision:{original['case_id']}",
            "source": original["source"],
            "question": original["question"],
            "scope_db": db,
            "category": "same_scope_collision",
            "target_objects": [focus],
            "collision_objects": collisions,
            "candidates": candidates,
        })
    if limit is not None:
        cases = cases[:limit]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_raw_sha256": file_sha256(raw_path),
        "ddl_sha256": {db: file_sha256(ddl_root / db / f"{db}.sql") for db in DATABASES},
        "cases": cases,
        "claim_boundary": "Deterministic gold-SQL focus-object proxy with same-scope schema collisions; not semantic-alias truth.",
    }
    output_raw.parent.mkdir(parents=True, exist_ok=True)
    output_raw.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def _collision_before(case: dict[str, Any], order: list[int]) -> float:
    target = case["target_objects"][0]
    target_key = (target["table"], target["identifier"])
    target_norm = normalize(target["identifier"])
    positions = [position for position, index in enumerate(order) if candidate_key(case["candidates"][index]) == (case["scope_db"], *target_key)]
    if not positions:
        return 0.0
    first = positions[0]
    return float(any(
        case["candidates"][index]["db"] == case["scope_db"]
        and normalize(case["candidates"][index]["identifier"]) == target_norm
        and (case["candidates"][index]["table"], case["candidates"][index]["identifier"]) != target_key
        for index in order[:first]
    ))


def _metrics(case: dict[str, Any], order: list[int]) -> dict[str, Any]:
    target = candidate_key(case["target_objects"][0])
    positions = [position for position, index in enumerate(order, start=1) if candidate_key(case["candidates"][index]) == target]
    first = positions[0] if positions else None
    return {
        "mrr": round(1.0 / first, 6) if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "same_scope_collision_before_target": _collision_before(case, order),
        "wrong_system_before_target": 0.0,
    }


def _aggregate_collision(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(key: str) -> float:
        return round(sum(float(row[key]) for row in rows) / len(rows), 6) if rows else 0.0
    return {
        "cases": len(rows),
        "mrr": mean("mrr"),
        "recall_at_1": mean("recall_at_1"),
        "recall_at_5": mean("recall_at_5"),
        "same_scope_collision_before_target": mean("same_scope_collision_before_target"),
    }


def run(raw_path: Path, result_path: Path, raw_dir: Path, *, endpoint: str, model: str, timeout_seconds: int) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    cases = raw["cases"]
    if not cases:
        raise ValueError("no same-scope collision cases")
    raw_dir.mkdir(parents=True, exist_ok=True)
    texts: list[str] = []
    text_keys: list[tuple[str, int, int]] = []
    for case_index, case in enumerate(cases):
        texts.append(f"database {case['scope_db']} question {case['question']}")
        text_keys.append(("query", case_index, -1))
        for candidate_index, candidate in enumerate(case["candidates"]):
            texts.append(f"database {candidate['db']} table {candidate['table']} identifier {candidate['identifier']}")
            text_keys.append(("candidate", case_index, candidate_index))
    vectors = post_embed(endpoint, texts)
    queries = {case_index: vectors[position] for position, (kind, case_index, _) in enumerate(text_keys) if kind == "query"}
    candidate_vectors = {(case_index, candidate_index): vectors[position] for position, (kind, case_index, candidate_index) in enumerate(text_keys) if kind == "candidate"}
    arms: dict[str, list[dict[str, Any]]] = {"exact_scope": [], "lexical_scope": [], "dense_scope": [], "frontier_scope": []}
    per_case: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    for case_index, case in enumerate(cases):
        candidates = case["candidates"]
        exact_order = sorted(range(len(candidates)), key=lambda index: (not exact_surface(case["question"], candidates[index]["identifier"]), candidates[index]["db"] != case["scope_db"], index))
        lexical_order = sorted(range(len(candidates)), key=lambda index: (-lexical_score(case["question"], candidates[index]), candidates[index]["db"] != case["scope_db"], index))
        dense_order = sorted(range(len(candidates)), key=lambda index: (-cosine(queries[case_index], candidate_vectors[(case_index, index)]), candidates[index]["db"] != case["scope_db"], index))
        prompt = _prompt(case, candidates)
        raw_response = raw_dir / f"case-{case_index:03d}.json"
        response = _call_frontier(prompt, model, timeout_seconds, raw_response)
        frontier_order, _ = _order_from_scores(response["scores"], len(candidates))
        orders = {"exact_scope": exact_order, "lexical_scope": lexical_order, "dense_scope": dense_order, "frontier_scope": frontier_order}
        metrics = {arm: _metrics(case, order) for arm, order in orders.items()}
        for arm in arms:
            arms[arm].append(metrics[arm])
        per_case.append({
            "case_id": case["case_id"],
            "candidate_fingerprints": [candidate_fingerprint(item) for item in candidates],
            "target_fingerprints": [candidate_fingerprint(item) for item in case["target_objects"]],
            "orders": {arm: list(order) for arm, order in orders.items()},
            "metrics": metrics,
            "frontier_decision": response.get("decision"),
            "frontier_decision_correct": response.get("decision") == "retrieve",
        })
        calls.append({"case": case_index, "status": "ok", "prompt_sha256": stable_hash(prompt), "raw_sha256": file_sha256(raw_response)})
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"raw_sha256": file_sha256(raw_path), "selected_cases": len(cases), "categories": {"same_scope_collision": len(cases)}, "raw_content_committed": False},
        "protocol": {"candidate_generation": "focus gold object + all same-scope normalized-name collisions + lexical distractors", "focus_label": "gold-SQL proxy, not semantic truth", "frontier_sees_gold_targets": False, "frontier_sees_source_row_ids": False, "model": model, "embedding_model": EMBED_MODEL, "raw_model_outputs_external": True},
        "aggregate": {arm: _aggregate_collision(values) for arm, values in arms.items()},
        "frontier_decision": {"retrieve_rate": round(sum(row["frontier_decision"] == "retrieve" for row in per_case) / len(per_case), 6)},
        "frontier_calls": {"requested": len(cases), "completed": len(cases), "failures": 0, "receipts": calls},
        "per_case": per_case,
        "claim_boundary": "Same-scope collision ranking on public NL2SQL with deterministic gold-SQL focus proxies. It does not establish semantic alias truth or downstream agent utility.",
    }
    result["result_sha256"] = stable_hash(result)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(cases), "aggregate": result["aggregate"], "result_sha256": result["result_sha256"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-raw", type=Path, required=True)
    parser.add_argument("--ddl-root", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()
    build_cases(args.source_raw, args.ddl_root, args.raw, limit=args.limit)
    run(args.raw, args.result, args.raw_dir, endpoint=args.endpoint, model=args.model, timeout_seconds=args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
