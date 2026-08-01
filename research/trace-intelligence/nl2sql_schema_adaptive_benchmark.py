#!/usr/bin/env python3
"""Schema-grounded adaptation benchmark for public NL2SQL retrieval.

This is a retrieval-only experiment.  It intentionally separates the newer
schema-adaptation hypothesis from the earlier MATM trajectory proxy result:
training positives are generated from held-in schemas, hard negatives are
mined at table/column granularity, and evaluation uses real held-out Defog
questions with gold-SQL focus objects.  Raw questions and SQL never enter the
committed receipt.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from nl2sql_real_alias_benchmark import EMBED_MODEL, cosine, post_embed, stable_hash
from nl2sql_real_alias_cohort import gold_targets, normalize, schema_from_ddl


SCHEMA_VERSION = "frankengate-nl2sql-schema-adaptive-retrieval-v2"
DBS = ("broker", "car_dealership", "derm_treatment", "ewallet")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def words(value: str) -> list[str]:
    return [item.lower() for item in WORD_RE.findall(value)]


def readable(value: str) -> str:
    return " ".join(value.replace("_", " ").split()).lower()


def doc_key(doc: dict[str, str]) -> tuple[str, str, str]:
    return doc["db"], doc["table"], doc["identifier"]


def doc_text(doc: dict[str, str]) -> str:
    if doc["granularity"] == "table":
        return f"database {doc['db']} relation {doc['table']} table"
    return f"database {doc['db']} relation {doc['table']} column {doc['identifier']}"


def make_docs(schemas: dict[str, dict[str, list[str]]]) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    for db in sorted(schemas):
        for table, columns in sorted(schemas[db].items()):
            docs.append({"db": db, "table": table, "identifier": table, "granularity": "table"})
            docs.extend(
                {"db": db, "table": table, "identifier": column, "granularity": "column"}
                for column in sorted(columns)
            )
    return docs


def generated_queries(doc: dict[str, str]) -> list[str]:
    table = readable(doc["table"])
    identifier = readable(doc["identifier"])
    if doc["granularity"] == "table":
        return [
            f"list records from the {table} table",
            f"show rows in {table}",
            f"which relation contains {table} information",
        ]
    return [
        f"what is the {identifier} in each {table} record",
        f"return {identifier} for the {table} table",
        f"filter {table} by {identifier}",
    ]


def lexical_score(question: str, doc: dict[str, str]) -> float:
    q = set(words(question))
    d = set(words(doc["table"]) + words(doc["identifier"]))
    exact = sum(normalize(token) == normalize(doc["identifier"]) for token in q)
    return exact * 10.0 + len(q & d) + (0.5 if normalize(doc["table"]) in {normalize(x) for x in q} else 0.0)


def exact_scope_score(question: str, doc: dict[str, str], scope_db: str) -> float:
    """Exact surface match with the known database scope as a first lane."""
    surface = any(normalize(token) == normalize(doc["identifier"]) for token in words(question))
    return (100.0 if surface and doc["db"] == scope_db else 0.0) + lexical_score(question, doc)


def batch_embed(endpoint: str, texts: Sequence[str], batch_size: int) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(post_embed(endpoint, texts[start : start + batch_size]))
    return vectors


def pair_features(query: np.ndarray, doc: np.ndarray) -> np.ndarray:
    # Product and absolute difference are the same low-level pair features used
    # in the earlier diagnostic, but their positives/negatives are now
    # schema-grounded instead of trajectory-similarity proxies.
    return np.concatenate((query * doc, np.abs(query - doc)))


def rank_metrics(case: dict[str, Any], order: Sequence[int]) -> dict[str, float]:
    target = tuple(case["target"])
    candidates = case["candidates"]
    positions = [
        position
        for position, index in enumerate(order, 1)
        if doc_key(candidates[index]) == target
    ]
    first = positions[0] if positions else None
    collision_before = 0.0
    wrong_scope_before = 0.0
    if first:
        target_doc = candidates[order[first - 1]]
        target_norm = normalize(target_doc["identifier"])
        before = [candidates[index] for index in order[: first - 1]]
        collision_before = float(
            any(
                item["db"] == case["scope_db"]
                and item["granularity"] == target_doc["granularity"]
                and normalize(item["identifier"]) == target_norm
                and item["table"] != target_doc["table"]
                for item in before
            )
        )
        wrong_scope_before = float(
            any(
                item["db"] != case["scope_db"]
                and normalize(item["identifier"]) == target_norm
                for item in before
            )
        )
    return {
        "mrr": 1.0 / first if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "recall_at_10": float(first is not None and first <= 10),
        "same_scope_collision_before_target": collision_before,
        "wrong_scope_collision_before_target": wrong_scope_before,
    }


def aggregate(rows: list[dict[str, float]]) -> dict[str, Any]:
    return {
        "cases": len(rows),
        **{
            key: round(sum(row[key] for row in rows) / len(rows), 6) if rows else 0.0
            for key in rows[0]
        },
    }


def rank(scores: Sequence[float]) -> list[int]:
    return sorted(range(len(scores)), key=lambda index: (-float(scores[index]), index))


def load_test_cases(
    *,
    source_root: Path,
    cohort_manifest: Path,
    schemas: dict[str, dict[str, list[str]]],
    docs: list[dict[str, str]],
) -> list[dict[str, Any]]:
    manifest = json.loads(cohort_manifest.read_text(encoding="utf-8"))
    handles: dict[str, list[dict[str, str]]] = {}
    for source_name in {task["source_file"] for task in manifest["tasks"]}:
        with (source_root / source_name).open(encoding="utf-8", newline="") as handle:
            handles[source_name] = list(csv.DictReader(handle))
    by_db = {db: [doc for doc in docs if doc["db"] == db] for db in DBS}
    cases: list[dict[str, Any]] = []
    for task in manifest["tasks"]:
        row = handles[task["source_file"]][int(task["source_row_0based"])]
        db = task["db_name"]
        targets = gold_targets(row["query"], schemas[db])
        for target in targets:
            target_doc = {
                "db": db,
                "table": target["table"],
                "identifier": target["identifier"],
                "granularity": "table" if target["table"] == target["identifier"] else "column",
            }
            if doc_key(target_doc) not in {doc_key(doc) for doc in by_db[db]}:
                continue
            cases.append(
                {
                    "case_id": hashlib.sha256(
                        f"{task['task_id']}\0{target_doc['table']}\0{target_doc['identifier']}".encode()
                    ).hexdigest(),
                    "scope_db": db,
                    "question": row["question"],
                    "target": list(doc_key(target_doc)),
                    "candidates": docs,
                }
            )
    return cases


def run(
    *,
    source_root: Path,
    ddl_root: Path,
    cohort_manifest: Path,
    output: Path,
    endpoint: str,
    batch_size: int,
    C: float,
) -> dict[str, Any]:
    schemas = {db: schema_from_ddl(ddl_root / db / f"{db}.sql") for db in DBS}
    docs = make_docs(schemas)
    cases = load_test_cases(
        source_root=source_root,
        cohort_manifest=cohort_manifest,
        schemas=schemas,
        docs=docs,
    )
    if not cases:
        raise ValueError("no held-out cases")

    doc_vectors = batch_embed(endpoint, [doc_text(doc) for doc in docs], batch_size)
    doc_by_key = {doc_key(doc): np.asarray(vector) for doc, vector in zip(docs, doc_vectors)}
    synthetic: list[tuple[str, tuple[str, str, str]]] = []
    for doc in docs:
        for query in generated_queries(doc):
            synthetic.append((query, doc_key(doc)))
    synth_vectors = batch_embed(endpoint, [query for query, _ in synthetic], batch_size)
    synth_by_db: dict[str, list[tuple[np.ndarray, tuple[str, str, str]]]] = defaultdict(list)
    for (query, target), vector in zip(synthetic, synth_vectors):
        synth_by_db[target[0]].append((np.asarray(vector), target))

    by_db: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_db[case["scope_db"]].append(case)
    folds: list[dict[str, Any]] = []
    for held_out in DBS:
        train_docs = [doc for doc in docs if doc["db"] != held_out]
        train_keys = {doc_key(doc) for doc in train_docs}
        train_x: list[np.ndarray] = []
        train_y: list[int] = []
        for query_vector, target in [
            item for db, items in synth_by_db.items() if db != held_out for item in items
        ]:
            if target not in train_keys:
                continue
            target_vector = doc_by_key[target]
            train_x.append(pair_features(query_vector, target_vector))
            train_y.append(1)
            # Hard negatives: high-similarity wrong objects, same-surface
            # collisions, and granularity-conflict siblings.
            scored = sorted(
                [
                    (cosine(query_vector, doc_by_key[doc_key(doc)]), doc)
                    for doc in train_docs
                    if doc_key(doc) != target
                ],
                key=lambda item: -item[0],
            )
            negatives: list[dict[str, str]] = []
            for _, candidate in scored:
                if candidate["db"] == target[0] and (
                    normalize(candidate["identifier"]) == normalize(target[2])
                    or candidate["table"] == target[1]
                    or candidate["granularity"] != ("table" if target[1] == target[2] else "column")
                ):
                    negatives.append(candidate)
                if len(negatives) >= 5:
                    break
            for candidate in negatives:
                train_x.append(pair_features(query_vector, doc_by_key[doc_key(candidate)]))
                train_y.append(0)
        scaler = StandardScaler()
        model = LogisticRegression(C=C, class_weight="balanced", max_iter=500, random_state=0)
        train_scaled = scaler.fit_transform(np.asarray(train_x))
        model.fit(train_scaled, train_y)

        held_out_cases = by_db.get(held_out, [])
        held_out_vectors = batch_embed(endpoint, [case["question"] for case in held_out_cases], batch_size)
        mode_rows: dict[str, dict[str, list[dict[str, float]]]] = defaultdict(lambda: defaultdict(list))
        for case, query_vector_value in zip(held_out_cases, held_out_vectors):
            query_vector = np.asarray(query_vector_value)
            candidate_modes = {
                "scope_filtered": [doc for doc in docs if doc["db"] == case["scope_db"]],
                "pooled": docs,
            }
            for mode, mode_docs in candidate_modes.items():
                exact_scores = [exact_scope_score(case["question"], doc, case["scope_db"]) for doc in mode_docs]
                lexical_scores = [lexical_score(case["question"], doc) for doc in mode_docs]
                frozen_scores = [cosine(query_vector, doc_by_key[doc_key(doc)]) for doc in mode_docs]
                adapted_scores = [
                    float(
                        model.decision_function(
                            scaler.transform(
                                pair_features(query_vector, doc_by_key[doc_key(doc)]).reshape(1, -1)
                            )
                        )[0]
                    )
                    for doc in mode_docs
                ]
                mode_case = {**case, "candidates": mode_docs}
                for arm, scores in zip(
                    ("exact_scope", "lexical", "frozen_embedding", "schema_adaptive_pair_scorer"),
                    (exact_scores, lexical_scores, frozen_scores, adapted_scores),
                ):
                    mode_rows[mode][arm].append(rank_metrics(mode_case, rank(scores)))
        folds.append(
            {
                "held_out_database": held_out,
                "train_synthetic_queries": sum(len(items) for db, items in synth_by_db.items() if db != held_out),
                "test_cases": len(held_out_cases),
                "modes": {
                    mode: {arm: aggregate(rows) for arm, rows in arm_map.items()}
                    for mode, arm_map in mode_rows.items()
                },
            }
        )

    aggregate_by_arm: dict[str, dict[str, Any]] = {}
    arms = ("exact_scope", "lexical", "frozen_embedding", "schema_adaptive_pair_scorer")
    for mode in ("scope_filtered", "pooled"):
        aggregate_by_arm[mode] = {}
        for arm in arms:
            fold_rows = [fold["modes"][mode][arm] for fold in folds]
            aggregate_by_arm[mode][arm] = {
                "folds": len(fold_rows),
                **{
                    key: round(sum(row[key] for row in fold_rows) / len(fold_rows), 6)
                    for key in fold_rows[0]
                    if key != "cases"
                },
                "cases": sum(row["cases"] for row in fold_rows),
            }
    source_files = sorted(
        {
            task["source_file"]
            for task in json.loads(cohort_manifest.read_text(encoding="utf-8"))["tasks"]
        }
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "source_root": "external-pinned-defog-checkout",
            "source_file_sha256": {name: sha256_file(source_root / name) for name in source_files},
            "ddl_sha256": {db: sha256_file(ddl_root / db / f"{db}.sql") for db in DBS},
            "cohort_manifest_sha256": sha256_file(cohort_manifest),
            "documents": len(docs),
            "cases": len(cases),
            "raw_content_committed": False,
        },
        "protocol": {
            "split": "leave-one-database-family-out",
            "training_positives": "schema-generated table/column queries",
            "hard_negatives": "same-surface, same-table, high-cosine, and granularity-conflict objects",
            "embedding_model": EMBED_MODEL,
            "adapter": "regularized logistic pair scorer over schema-grounded query/document product+difference features",
            "C": C,
            "candidate_pool": "scope-filtered and all public schema objects across four databases",
        },
        "aggregate": aggregate_by_arm,
        "folds": folds,
        "claim_boundary": "Schema-grounded public retrieval diagnostic; no SME semantic-alias truth, agent utility, or production embedding claim.",
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "aggregate": aggregate_by_arm, "result_sha256": result["result_sha256"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ddl-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--C", type=float, default=0.1)
    args = parser.parse_args()
    run(
        source_root=args.source_root,
        ddl_root=args.ddl_root,
        cohort_manifest=args.cohort_manifest,
        output=args.output,
        endpoint=args.endpoint,
        batch_size=args.batch_size,
        C=args.C,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
