#!/usr/bin/env python3
"""Audit EnterpriseRAG-Bench question coverage without copying question text."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


SCHEMA_VERSION = "frankengate-enterprise-rag-question-audit-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def audit(path: Path) -> dict[str, Any]:
    rows = pq.read_table(path).to_pylist()
    question_types = Counter(str(row["question_type"]) for row in rows)
    source_types = Counter()
    source_combinations = Counter()
    expected_doc_count = 0
    multi_document_questions = 0
    answer_fact_count = 0
    empty_source_types = 0
    malformed = []
    for row in rows:
        sources = tuple(sorted(str(item) for item in (row.get("source_types") or [])))
        source_combinations["+".join(sources) if sources else "<none>"] += 1
        if not sources:
            empty_source_types += 1
        for source in sources:
            source_types[source] += 1
        docs = row.get("expected_doc_ids") or []
        facts = row.get("answer_facts") or []
        expected_doc_count += len(docs)
        answer_fact_count += len(facts)
        multi_document_questions += len(docs) > 1
        required = ("question_id", "question_type", "question", "expected_doc_ids", "gold_answer", "answer_facts")
        missing = [name for name in required if name not in row or row[name] is None]
        if missing:
            malformed.append({"question_id": row.get("question_id"), "missing": missing})
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"questions_sha256": sha256(path), "raw_question_text_committed": False},
        "dataset": {
            "rows": len(rows),
            "question_types": dict(sorted(question_types.items())),
            "source_type_question_counts": dict(sorted(source_types.items())),
            "source_combinations": dict(sorted(source_combinations.items())),
            "expected_document_references": expected_doc_count,
            "multi_document_questions": multi_document_questions,
            "answer_facts": answer_fact_count,
            "questions_without_source_types": empty_source_types,
            "required_field_errors": len(malformed),
        },
        "coverage_slices": {
            "retrieval_and_reasoning": ["basic", "semantic", "intra_document_reasoning", "project_related", "high_level"],
            "safety_and_temporal": ["constrained", "conflicting_info", "info_not_found"],
            "evidence_completeness": ["completeness"],
            "other": ["miscellaneous"],
        },
        "claim_boundary": {
            "document_retrieval_fixture_characterized": True,
            "trace_learning_measured": False,
            "ontology_quality_measured": False,
            "skill_improvement_measured": False,
            "authority_leakage_measured": False,
            "reason": "Question parquet contains authored questions, expected document IDs, answers, and facts, but no user trajectories, tool outcomes, exposure decisions, principals, or changed-system replay.",
        },
        "malformed_examples": malformed[:20],
    }
    result["audit_sha256"] = stable_hash(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.questions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["dataset"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
