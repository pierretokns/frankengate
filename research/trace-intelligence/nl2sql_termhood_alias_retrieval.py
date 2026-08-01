#!/usr/bin/env python3
"""Test train-only termhood associations as a held-out search alias field.

This is a compositional public-proxy experiment: the modern termhood port
selects question n-grams, gold SQL in the training split associates selected
phrases with schema objects, and retrieval is evaluated on a separate
within-schema split. No aliases are invented at query time and no held-out
question is used to build the mapping.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from modern_term_acronym_port import STOP, stable_hash, termhood, tokens
from nl2sql_real_alias_cohort import lexical_score


SCHEMA_VERSION = "frankengate-nl2sql-termhood-alias-retrieval-v1"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(candidate: dict[str, str]) -> tuple[str, str, str]:
    return str(candidate["db"]), str(candidate["table"]), str(candidate["identifier"])


def ngram_hashes(text: str, *, max_n: int = 4) -> dict[str, str]:
    words = [word for word in tokens(text) if word not in STOP]
    output: dict[str, str] = {}
    for n in range(1, max_n + 1):
        for index in range(len(words) - n + 1):
            phrase = " ".join(words[index : index + n])
            output[stable_hash(phrase)] = phrase
    return output


def target_keys(case: dict[str, Any]) -> set[tuple[str, str, str]]:
    db = str(case["scope_db"])
    return {(db, str(target["table"]), str(target["identifier"])) for target in case.get("target_objects", [])}


def rank_metrics(case: dict[str, Any], order: list[int]) -> dict[str, float]:
    candidates = case["candidates"]
    targets = target_keys(case)
    positions = [position for position, index in enumerate(order, 1) if key(candidates[index]) in targets]
    first = positions[0] if positions else None
    before = [candidates[index] for index in order[: first - 1]] if first else []
    target = candidates[order[first - 1]] if first else None
    same_scope_collision = 0.0
    wrong_scope_collision = 0.0
    if target:
        norm = str(target["identifier"]).lower().replace("_", "")
        same_scope_collision = float(any(
            item["db"] == case["scope_db"] and item["table"] != target["table"]
            and str(item["identifier"]).lower().replace("_", "") == norm for item in before
        ))
        wrong_scope_collision = float(any(
            item["db"] != case["scope_db"]
            and str(item["identifier"]).lower().replace("_", "") == norm for item in before
        ))
    return {
        "mrr": 1.0 / first if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "same_scope_collision_before_target": same_scope_collision,
        "wrong_scope_collision_before_target": wrong_scope_collision,
    }


def aggregate(rows: list[dict[str, float]]) -> dict[str, Any]:
    return {
        "cases": len(rows),
        **{
            metric: round(sum(row[metric] for row in rows) / len(rows), 6) if rows else 0.0
            for metric in rows[0]
        },
    }


def build_mapping(train: list[dict[str, Any]], *, limit: int) -> tuple[dict[str, set[tuple[str, str, str]]], dict[str, Any]]:
    foreground = [str(case["question"]) for case in train]
    background = [str(case["question"]) for case in train]
    candidates = termhood(foreground, background, limit=limit)
    admitted = {row["term_hash"] for row in candidates}
    mapping: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    association_count = 0
    for case in train:
        target_set = target_keys(case)
        for term_hash in ngram_hashes(str(case["question"])):
            if term_hash not in admitted:
                continue
            mapping[term_hash].update(target_set)
            association_count += len(target_set)
    return mapping, {
        "candidate_count": len(candidates),
        "positive_candidate_count": sum(row["score_bucket"] == "positive" for row in candidates),
        "mapped_term_count": len(mapping),
        "term_target_association_count": association_count,
    }


def run(raw: Path, output: Path, *, limit: int) -> dict[str, Any]:
    value = json.loads(raw.read_text(encoding="utf-8"))
    if value.get("schema_version") != "frankengate-nl2sql-real-alias-cohort-v1":
        raise ValueError("unexpected cohort schema")
    targeted = [case for case in value["cases"] if case.get("category") != "scope_swapped_nil"]
    by_db: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in targeted:
        by_db[str(case["scope_db"])].append(case)
    arms: dict[str, list[dict[str, float]]] = defaultdict(list)
    fold_summaries: list[dict[str, Any]] = []
    for db in sorted(by_db):
        ordered = sorted(by_db[db], key=lambda case: stable_hash(case["case_id"]))
        train, evaluation = ordered[::2], ordered[1::2]
        mapping, mapping_stats = build_mapping(train, limit=limit)
        fold_summaries.append({"db": db, "train_cases": len(train), "eval_cases": len(evaluation), **mapping_stats})
        for case in evaluation:
            candidates = case["candidates"]
            lexical_order = sorted(range(len(candidates)), key=lambda index: (-lexical_score(case["question"], candidates[index]), index))
            question_terms = ngram_hashes(str(case["question"]))
            alias_keys = set().union(*(mapping.get(term_hash, set()) for term_hash in question_terms)) if question_terms else set()
            enriched_order = sorted(
                range(len(candidates)),
                key=lambda index: (-lexical_score(case["question"], candidates[index]) - (20.0 if key(candidates[index]) in alias_keys else 0.0), index),
            )
            for arm, order in (("lexical", lexical_order), ("lexical_plus_termhood_alias", enriched_order)):
                arms[arm].append(rank_metrics(case, order))
    result = {
        "schema_version": SCHEMA_VERSION,
        "protocol": {
            "split": "within-schema deterministic case split",
            "mapping": "termhood-selected question n-grams associated only with training gold-SQL targets",
            "evaluation": "held-out candidate pools from the public cohort",
            "candidate_limit": limit,
            "alias_field": "search-only; no ontology, memory, or skill promotion",
        },
        "dataset": {
            "cohort_schema": "frankengate-nl2sql-real-alias-cohort-v1",
            "raw_sha256": file_sha256(raw),
            "targeted_case_count": len(targeted),
            "database_count": len(by_db),
        },
        "folds": fold_summaries,
        "arms": {arm: aggregate(rows) for arm, rows in sorted(arms.items())},
        "claim_boundary": {
            "semantic_alias_truth_established": False,
            "enterprise_quality_established": False,
            "downstream_agent_utility_established": False,
            "reason": "Gold-SQL objects are public retrieval targets; the experiment does not contain reviewed aliases, user outcomes, or changed-system replay.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["arms"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3000)
    args = parser.parse_args()
    run(args.raw, args.output, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
