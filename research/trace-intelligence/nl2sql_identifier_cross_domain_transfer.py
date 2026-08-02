#!/usr/bin/env python3
"""Evaluate identifier-aware SQL ranking across Defog and WMH-BIRD domains.

The ranker uses the same surface/scope/collision features as the Defog
identifier benchmark. This probe asks whether those features transfer between
two different SQL schema families, while keeping exact SQL focus labels as a
proxy and never claiming semantic alias truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from nl2sql_identifier_reranker_benchmark import (
    _rank_metrics,
    _fit,
    feature_row,
    lexical_score,
)
from wmh_bird_exposure_counterfactual import load_traces


SCHEMA_VERSION = "frankengate-nl2sql-identifier-cross-domain-transfer-v1"


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load_defog(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in payload["cases"] if row.get("target_objects") and row.get("candidates")]


def load_bird(traces_path: Path, manifest: Path) -> list[dict[str, Any]]:
    traces = load_traces(traces_path, manifest)
    cases: list[dict[str, Any]] = []
    for trace in traces:
        candidates = [
            {"db": trace.db_name, "table": table, "identifier": table}
            for table in sorted(trace.exposed_tables)
        ]
        targets = [table for table in sorted(trace.used_tables) if table in trace.exposed_tables]
        if not candidates or not targets:
            continue
        cases.append({
            "case_id": trace.trace_hash,
            "question": trace.prompt,
            "scope_db": trace.db_name,
            "candidates": candidates,
            "target_objects": [{"db": trace.db_name, "table": targets[0], "identifier": targets[0]}],
        })
    return cases


def aggregate(rows: list[dict[str, float]]) -> dict[str, Any]:
    if not rows:
        return {"cases": 0, "mrr": 0.0, "recall_at_1": 0.0, "recall_at_5": 0.0, "same_scope_collision_before_target": 0.0}
    return {
        "cases": len(rows),
        "mrr": round(sum(row["mrr"] for row in rows) / len(rows), 6),
        "recall_at_1": round(sum(row["recall_at_1"] for row in rows) / len(rows), 6),
        "recall_at_5": round(sum(row["recall_at_5"] for row in rows) / len(rows), 6),
        "same_scope_collision_before_target": round(sum(row["same_scope_collision_before_target"] for row in rows) / len(rows), 6),
    }


def evaluate(train: list[dict[str, Any]], test: list[dict[str, Any]]) -> dict[str, Any]:
    models = {
        "identifier_reranker": _fit(train, False),
        "hard_negative_reranker": _fit(train, True),
    }
    arms: dict[str, list[dict[str, float]]] = {name: [] for name in ("lexical", *models)}
    for case in test:
        pool = list(range(len(case["candidates"])))
        lexical_order = sorted(pool, key=lambda index: (-lexical_score(case["question"], case["candidates"][index]), index))
        arms["lexical"].append(_rank_metrics(case, lexical_order))
        matrix = np.asarray([feature_row(case, candidate, include_label=False) for candidate in case["candidates"]])
        for name, model in models.items():
            scores = model.predict_proba(matrix)[:, 1]
            order = sorted(pool, key=lambda index: (-float(scores[index]), index))
            arms[name].append(_rank_metrics(case, order))
    return {name: aggregate(rows) for name, rows in arms.items()}


def run(defog_path: Path, bird_traces: Path, bird_manifest: Path, output: Path) -> dict[str, Any]:
    defog = load_defog(defog_path)
    bird = load_bird(bird_traces, bird_manifest)
    directions = {
        "defog_to_bird": evaluate(defog, bird),
        "bird_to_defog": evaluate(bird, defog),
    }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "datasets": {
            "defog": {"cases": len(defog), "raw_sha256": hashlib.sha256(defog_path.read_bytes()).hexdigest(), "raw_content_committed": False},
            "wmh_bird": {"cases": len(bird), "traces_sha256": hashlib.sha256(bird_traces.read_bytes()).hexdigest(), "manifest_sha256": hashlib.sha256(bird_manifest.read_bytes()).hexdigest(), "raw_content_committed": False},
        },
        "protocol": {
            "features": "Defog identifier-aware surface/scope/collision features",
            "model": "sklearn LogisticRegression C=1 max_iter=1000 random_state=0",
            "positive": "first target object from recorded gold SQL focus proxy",
            "cross_domain_split": "train on all source cases, test on all target cases",
            "hard_negative_weight": 4.0,
        },
        "directions": directions,
        "claim_boundary": {
            "semantic_alias_labels": False,
            "changed_system_replay": False,
            "enterprise_transfer": False,
            "embedding_promotion": False,
            "reason": "This tests feature/ranker transfer between two public SQL proxies; database/table focus labels are not SME intent labels and the domains have different candidate constructions.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(directions, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--defog", type=Path, required=True)
    parser.add_argument("--bird-traces", type=Path, required=True)
    parser.add_argument("--bird-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.defog, args.bird_traces, args.bird_manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
