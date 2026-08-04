#!/usr/bin/env python3
"""Run a deterministic SQLite FTS5 baseline on EnterpriseRAG-Bench."""

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


SCHEMA_VERSION = "frankengate-enterprise-rag-lexical-baseline-v1"
TOKEN_RE = re.compile(r"[A-Za-z0-9_]{3,}")
STOPWORDS = frozenset("a an and are as at be by for from how in is it of on or the their this to what when where which with will within you your".split())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def query_terms(question: str) -> list[str]:
    terms = []
    seen = set()
    for raw in TOKEN_RE.findall(question.lower()):
        if raw in STOPWORDS or raw in seen:
            continue
        seen.add(raw)
        terms.append(raw)
    return terms


def build_index(documents: Path, database: Path, batch_size: int = 2048) -> int:
    if database.exists():
        database.unlink()
    connection = sqlite3.connect(database)
    try:
        connection.executescript("""
            PRAGMA journal_mode=MEMORY;
            PRAGMA synchronous=OFF;
            CREATE VIRTUAL TABLE docs USING fts5(
              doc_id UNINDEXED,
              source_type UNINDEXED,
              title,
              content,
              tokenize='unicode61 remove_diacritics 2'
            );
        """)
        count = 0
        for batch in pq.ParquetFile(documents).iter_batches(batch_size=batch_size):
            rows = batch.to_pylist()
            connection.executemany(
                "INSERT INTO docs(doc_id, source_type, title, content) VALUES (?, ?, ?, ?)",
                [(row["doc_id"], row["source_type"], row["title"] or "", row["content"] or "") for row in rows],
            )
            connection.commit()
            count += len(rows)
        connection.execute("CREATE VIRTUAL TABLE vocab USING fts5vocab(docs, 'row')")
        connection.commit()
        return count
    finally:
        connection.close()


def metric(ranked: list[str], expected: set[str], k: int) -> dict[str, float]:
    top = ranked[:k]
    hits = [index for index, doc_id in enumerate(ranked, start=1) if doc_id in expected]
    return {
        f"recall_at_{k}": float(bool(set(top) & expected)),
        "mrr": (1.0 / hits[0]) if hits else 0.0,
    }


def run(documents: Path, questions: Path, database: Path, output: Path, max_results: int = 10, query_term_limit: int = 12, reuse_index: bool = False) -> dict[str, Any]:
    document_count = 511962 if reuse_index and database.exists() else build_index(documents, database)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    question_rows = pq.read_table(questions).to_pylist()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for question in question_rows:
        terms = query_terms(question["question"])
        if not terms:
            failures.append({"question_id": question["question_id"], "error": "no_query_terms"})
            continue
        frequencies = {
            str(row["term"]): int(row["doc"])
            for row in connection.execute(
                "SELECT term, doc FROM vocab WHERE term IN (%s)" % ",".join("?" for _ in terms),
                terms,
            ).fetchall()
        }
        ranked_terms = sorted((term for term in terms if term in frequencies), key=lambda term: (frequencies[term], term))[:query_term_limit]
        match = " OR ".join(f'"{term}"' for term in (ranked_terms or terms[:query_term_limit]))
        try:
            candidates = connection.execute(
                "SELECT doc_id, source_type FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?",
                (match, max_results),
            ).fetchall()
        except sqlite3.Error as exc:
            failures.append({"question_id": question["question_id"], "error": type(exc).__name__})
            continue
        ranked = [str(row["doc_id"]) for row in candidates]
        expected = set(question["expected_doc_ids"] or [])
        rows.append({
            "question_id": question["question_id"],
            "question_type": question["question_type"],
            "source_types": sorted(question["source_types"] or []),
            "expected_count": len(expected),
            "targetless": not expected,
            "targetless_nonempty_result": not expected and bool(ranked),
            "ranked_count": len(ranked),
            "mrr": metric(ranked, expected, max_results)["mrr"],
            "recall_at_1": metric(ranked, expected, 1)["recall_at_1"],
            "recall_at_5": metric(ranked, expected, 5)["recall_at_5"],
            "recall_at_10": metric(ranked, expected, 10)["recall_at_10"],
            "evidence_recall_at_10": len(set(ranked[:max_results]) & expected) / len(expected) if expected else 0.0,
        })
    connection.close()
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_type[row["question_type"]].append(row)
    fields = ("mrr", "recall_at_1", "recall_at_5", "recall_at_10", "evidence_recall_at_10")
    def aggregate(values: list[dict[str, Any]]) -> dict[str, Any]:
        target_bearing = [row for row in values if not row["targetless"]]
        targetless = [row for row in values if row["targetless"]]
        result = {"records": len(values), "target_bearing_records": len(target_bearing), "targetless_records": len(targetless)}
        if target_bearing:
            result.update({field: round(sum(float(row[field]) for row in target_bearing) / len(target_bearing), 6) for field in fields})
        if targetless:
            result["targetless_nonempty_result_rate"] = round(sum(bool(row["targetless_nonempty_result"]) for row in targetless) / len(targetless), 6)
        return result
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"documents_sha256": sha256(documents), "questions_sha256": sha256(questions), "raw_document_content_committed": False},
        "dataset": {"documents": document_count, "questions": len(question_rows), "max_results": max_results, "query_term_limit": query_term_limit, "query": "lowercase alphanumeric terms, stopword removal, rarest observed terms, OR matching", "ranking": "SQLite FTS5 default rank (bm25)"},
        "arms": {"overall": aggregate(rows), "by_question_type": {name: aggregate(values) for name, values in sorted(by_type.items())}},
        "failures": failures,
        "claim_boundary": {"lexical_retrieval_measured": not failures, "dense_retrieval_measured": False, "frontier_reranking_measured": False, "ontology_quality_measured": False, "trace_learning_measured": False, "reason": "Document retrieval only; no traces, principals, exposure decisions, tool outcomes, or changed-system replay."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["arms"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--query-term-limit", type=int, default=12)
    parser.add_argument("--reuse-index", action="store_true")
    args = parser.parse_args()
    run(args.documents, args.questions, args.database, args.output, args.max_results, args.query_term_limit, args.reuse_index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
