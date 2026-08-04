#!/usr/bin/env python3
"""Evaluate the modern vocabulary port on a held-out NL2SQL schema.

The benchmark uses only the content-free public Defog alias-cohort receipt's
external raw file.  It measures whether terms mined from questions in three
databases cover gold-SQL target identifier surfaces in a fourth database.  A
miss is not a semantic-alias failure: the public cohort has no reviewed
enterprise aliases.  The purpose is to prevent a Wisp mechanics probe from
being mistaken for cross-schema vocabulary transfer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from modern_term_acronym_port import STOP, stable_hash, termhood, tokens


SCHEMA_VERSION = "frankengate-nl2sql-modern-vocabulary-benchmark-v1"
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def normalize_surface(value: str) -> str:
    return " ".join(value.replace("_", " ").lower().split())


def phrase_forms(value: str) -> set[str]:
    normalized = normalize_surface(value)
    forms = {normalized}
    if normalized.endswith("s") and len(normalized) > 3:
        forms.add(normalized[:-1])
    if normalized.endswith("ies") and len(normalized) > 4:
        forms.add(normalized[:-3] + "y")
    if normalized.endswith("es") and len(normalized) > 4:
        forms.add(normalized[:-2])
    return forms


def phrase_hashes(value: str) -> set[str]:
    forms = phrase_forms(value)
    return {stable_hash(" ".join(tokens(form))) for form in forms if form}


def question_contains(question: str, value: str) -> bool:
    words = [item for item in tokens(question) if item not in STOP]
    needle = [item for item in tokens(normalize_surface(value)) if item not in STOP]
    if not needle:
        return False
    return any(words[index : index + len(needle)] == needle for index in range(len(words) - len(needle) + 1))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases(raw: Path) -> list[dict[str, Any]]:
    value = json.loads(raw.read_text(encoding="utf-8"))
    if value.get("schema_version") != "frankengate-nl2sql-real-alias-cohort-v1":
        raise ValueError("unexpected cohort schema")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("raw cohort contains no cases")
    return cases


def score_targets(cases: list[dict[str, Any]], candidate_hashes: set[str]) -> tuple[int, int, int]:
    target_count = direct_count = termhood_count = 0
    for case in cases:
        for target in case.get("target_objects", []):
            target_count += 1
            identifier = str(target["identifier"])
            table = str(target["table"])
            forms = phrase_forms(identifier) | phrase_forms(table)
            direct = any(question_contains(case["question"], form) for form in forms)
            hit = bool(candidate_hashes & set().union(*(phrase_hashes(form) for form in forms)))
            direct_count += int(direct)
            termhood_count += int(hit)
    return target_count, direct_count, termhood_count


def run(raw: Path, output: Path, *, limit: int) -> dict[str, Any]:
    cases = load_cases(raw)
    by_db: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        if case.get("category") != "scope_swapped_nil":
            by_db[str(case["scope_db"])].append(case)
    databases = sorted(by_db)
    folds: list[dict[str, Any]] = []
    all_rows: list[dict[str, int]] = []
    for held_out in databases:
        foreground = [case["question"] for db, rows in by_db.items() if db != held_out for case in rows]
        background = [
            case["question"]
            for case in cases
            if case.get("category") == "scope_swapped_nil" and case.get("scope_db") != held_out
        ]
        candidates = termhood(foreground, background or foreground, limit=limit)
        target_count, direct_count, termhood_count = score_targets(by_db[held_out], {row["term_hash"] for row in candidates})
        folds.append(
            {
                "condition": "cross_schema",
                "held_out_db": held_out,
                "foreground_count": len(foreground),
                "background_count": len(background),
                "candidate_count": len(candidates),
                "positive_candidate_count": sum(row["score_bucket"] == "positive" for row in candidates),
                "target_count": target_count,
                "direct_surface_targets": direct_count,
                "termhood_targets": termhood_count,
            }
        )
        # A within-schema control asks whether the port can recover recurring
        # vocabulary when the target schema is actually represented in the
        # training questions.  This is still retrieval-target coverage, not
        # semantic alias truth.
        in_domain = sorted(by_db[held_out], key=lambda row: stable_hash(row["case_id"]))
        train_rows = in_domain[::2]
        eval_rows = in_domain[1::2]
        in_candidates = termhood(
            [row["question"] for row in train_rows],
            [row["question"] for row in cases if row.get("category") == "scope_swapped_nil" and row.get("scope_db") == held_out] or [row["question"] for row in train_rows],
            limit=limit,
        )
        in_target_count, in_direct_count, in_termhood_count = score_targets(eval_rows, {row["term_hash"] for row in in_candidates})
        folds.append(
            {
                "condition": "within_schema_control",
                "held_out_db": held_out,
                "foreground_count": len(train_rows),
                "background_count": sum(1 for row in cases if row.get("category") == "scope_swapped_nil" and row.get("scope_db") == held_out),
                "candidate_count": len(in_candidates),
                "positive_candidate_count": sum(row["score_bucket"] == "positive" for row in in_candidates),
                "target_count": in_target_count,
                "direct_surface_targets": in_direct_count,
                "termhood_targets": in_termhood_count,
            }
        )
        all_rows.extend(
            [
                {"target_count": target_count, "direct_surface_targets": direct_count, "termhood_targets": termhood_count},
                {"target_count": in_target_count, "direct_surface_targets": in_direct_count, "termhood_targets": in_termhood_count},
            ]
        )
    total_targets = sum(row["target_count"] for row in all_rows)
    total_direct = sum(row["direct_surface_targets"] for row in all_rows)
    total_termhood = sum(row["termhood_targets"] for row in all_rows)
    cross_rows = [row for row in folds if row["condition"] == "cross_schema"]
    control_rows = [row for row in folds if row["condition"] == "within_schema_control"]
    def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
        targets = sum(row["target_count"] for row in rows)
        direct = sum(row["direct_surface_targets"] for row in rows)
        mined = sum(row["termhood_targets"] for row in rows)
        return {
            "target_count": targets,
            "direct_surface_targets": direct,
            "termhood_targets": mined,
            "direct_surface_recall": round(direct / targets, 6) if targets else 0.0,
            "termhood_recall": round(mined / targets, 6) if targets else 0.0,
        }
    result = {
        "schema_version": SCHEMA_VERSION,
        "protocol": {
            "split": "database-held-out",
            "foreground": "targeted questions from the other databases",
            "background": "scope-swapped NIL questions from the other databases",
            "candidate_limit": limit,
            "target_definition": "gold-SQL objects in the external cohort",
        },
        "dataset": {
            "cohort_schema": "frankengate-nl2sql-real-alias-cohort-v1",
            "raw_sha256": sha256_file(raw),
            "case_count": len(cases),
            "targeted_case_count": sum(len(rows) for rows in by_db.values()),
            "database_count": len(databases),
        },
        "folds": folds,
        "aggregate": {
            "cross_schema": metrics(cross_rows),
            "within_schema_control": metrics(control_rows),
            "combined": {
                "target_count": total_targets,
                "direct_surface_targets": total_direct,
                "termhood_targets": total_termhood,
                "direct_surface_recall": round(total_direct / total_targets, 6) if total_targets else 0.0,
                "termhood_recall": round(total_termhood / total_targets, 6) if total_targets else 0.0,
            },
        },
        "claim_boundary": {
            "enterprise_alias_quality_established": False,
            "semantic_alias_truth_established": False,
            "cross_schema_transfer_established": False,
            "reason": "Gold-SQL target objects are retrieval targets, not reviewed aliases; this is a public schema-transfer diagnostic.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
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
