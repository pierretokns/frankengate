#!/usr/bin/env python3
"""Measure the oracle source-type filter ceiling on EnterpriseRAG-Bench.

This is deliberately an upper-bound diagnostic, not a production metadata
retriever: the benchmark publishes ``source_types`` with each question.  The
receipt therefore keeps the filter marked as oracle and does not claim alias,
authority, or trace-learning value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


SCHEMA_VERSION = "frankengate-enterprise-rag-source-filter-ceiling-v1"
TOKEN_RE = re.compile(r"[A-Za-z0-9_]{3,}")
STOPWORDS = frozenset(
    "a an and are as at be by for from how in is it of on or the their this to what when where which with will within you your".split()
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def query_terms(question: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for token in TOKEN_RE.findall(question.lower()):
        if token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def ranked_rows(connection: sqlite3.Connection, question: dict[str, Any], top_k: int, term_limit: int, source_types: list[str] | None) -> list[tuple[str, str]]:
    terms = query_terms(str(question["question"]))
    if not terms:
        return []
    frequencies = {
        str(row["term"]): int(row["doc"])
        for row in connection.execute(
            "SELECT term, doc FROM vocab WHERE term IN (%s)" % ",".join("?" for _ in terms),
            terms,
        ).fetchall()
    }
    selected = sorted((term for term in terms if term in frequencies), key=lambda term: (frequencies[term], term))[:term_limit]
    match = " OR ".join(f'"{term}"' for term in (selected or terms[:term_limit]))
    if source_types:
        placeholders = ",".join("?" for _ in source_types)
        sql = f"SELECT doc_id, source_type FROM docs WHERE docs MATCH ? AND source_type IN ({placeholders}) ORDER BY rank LIMIT ?"
        params: list[Any] = [match, *source_types, top_k]
    else:
        sql = "SELECT doc_id, source_type FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?"
        params = [match, top_k]
    return [(str(row["doc_id"]), str(row["source_type"])) for row in connection.execute(sql, params).fetchall()]


def metrics(ranked: list[tuple[str, str]], expected: set[str], expected_sources: set[str], top_k: int) -> dict[str, Any]:
    ids = [doc_id for doc_id, _ in ranked]
    hits = [index for index, doc_id in enumerate(ids, start=1) if doc_id in expected]
    top = ranked[:top_k]
    wrong_source = sum(source not in expected_sources for _, source in top) if expected_sources else 0
    same_source_non_target = sum(source in expected_sources and doc_id not in expected for doc_id, source in top) if expected_sources else 0
    return {
        "mrr": 1.0 / hits[0] if hits else 0.0,
        "recall_at_1": float(bool(set(ids[:1]) & expected)),
        "recall_at_5": float(bool(set(ids[:5]) & expected)),
        "recall_at_10": float(bool(set(ids[:10]) & expected)),
        "evidence_recall_at_10": len(set(ids[:10]) & expected) / len(expected) if expected else 0.0,
        "invalid_extra_at_10": sum(doc_id not in expected for doc_id, _ in top) if expected else 0,
        "wrong_source_extra_at_10": wrong_source,
        "same_source_non_target_at_10": same_source_non_target,
        "ranked_count": len(ranked),
    }


def aggregate(rows: list[dict[str, Any]], metric_name: str) -> dict[str, Any]:
    target = [row for row in rows if not row["targetless"]]
    targetless = [row for row in rows if row["targetless"]]
    result: dict[str, Any] = {"records": len(rows), "target_bearing_records": len(target), "targetless_records": len(targetless)}
    if target:
        fields = ("mrr", "recall_at_1", "recall_at_5", "recall_at_10", "evidence_recall_at_10", "invalid_extra_at_10", "wrong_source_extra_at_10", "same_source_non_target_at_10")
        result.update({field: round(sum(float(row[metric_name][field]) for row in target) / len(target), 6) for field in fields})
    if targetless:
        result["targetless_nonempty_result_rate"] = round(sum(bool(row[metric_name]["ranked_count"]) for row in targetless) / len(targetless), 6)
    return result


def run(database: Path, questions: Path, output: Path, top_k: int = 10, term_limit: int = 12, max_questions: int | None = None, per_question_type: int | None = None) -> dict[str, Any]:
    question_rows = pq.read_table(questions).to_pylist()
    if per_question_type is not None:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for question in question_rows:
            grouped[str(question["question_type"])].append(question)
        question_rows = [question for question_type in sorted(grouped) for question in grouped[question_type][:per_question_type]]
    if max_questions is not None:
        question_rows = question_rows[:max_questions]
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows: list[dict[str, Any]] = []
    try:
        for question in question_rows:
            expected = {str(item) for item in (question.get("expected_doc_ids") or [])}
            expected_sources = {str(item) for item in (question.get("source_types") or [])}
            filtered_sources = sorted(expected_sources) if expected_sources else None
            unfiltered = ranked_rows(connection, question, top_k, term_limit, None)
            filtered = ranked_rows(connection, question, top_k, term_limit, filtered_sources)
            rows.append({
                "question_id": str(question["question_id"]),
                "question_type": str(question["question_type"]),
                "targetless": not expected,
                "oracle_filter_available": bool(filtered_sources),
                "unfiltered": metrics(unfiltered, expected, expected_sources, top_k),
                "oracle_source_filtered": metrics(filtered, expected, expected_sources, top_k),
            })
    finally:
        connection.close()

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_type[row["question_type"]].append(row)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "database_sha256": file_sha256(database),
            "questions_sha256": file_sha256(questions),
            "raw_document_content_committed": False,
            "raw_question_text_committed": False,
        },
        "dataset": {"questions": len(rows), "top_k": top_k, "term_limit": term_limit, "database_read_only": True},
        "protocol": {
            "query": "same rare-term OR FTS5 query as lexical baseline",
            "unfiltered_arm": "full-corpus lexical retrieval",
            "filtered_arm": "source_type IN question.source_types",
            "filter_is_oracle": True,
            "filter_is_not_authorization": True,
        },
        "arms": {
            "overall": {
                "unfiltered": aggregate(rows, "unfiltered"),
                "oracle_source_filtered": aggregate(rows, "oracle_source_filtered"),
            },
            "by_question_type": {
                question_type: {
                    "unfiltered": aggregate(group, "unfiltered"),
                    "oracle_source_filtered": aggregate(group, "oracle_source_filtered"),
                }
                for question_type, group in sorted(by_type.items())
            },
        },
        "claim_boundary": {
            "oracle_metadata_ceiling_measured": True,
            "production_metadata_retrieval_measured": False,
            "hard_negative_semantic_labels_established": False,
            "ontology_quality_measured": False,
            "trace_learning_measured": False,
            "artifact_utility_measured": False,
            "reason": "source_types are benchmark-provided answer metadata; the filtered arm is an upper bound, not a learned alias or authorization system",
        },
        "rows": rows,
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["arms"]["overall"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--term-limit", type=int, default=12)
    parser.add_argument("--max-questions", type=int, default=None)
    parser.add_argument("--per-question-type", type=int, default=None)
    args = parser.parse_args()
    run(args.database, args.questions, args.output, args.top_k, args.term_limit, args.max_questions, args.per_question_type)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
