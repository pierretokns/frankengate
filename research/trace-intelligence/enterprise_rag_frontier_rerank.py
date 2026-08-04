#!/usr/bin/env python3
"""Frontier reranking of the EnterpriseRAG-Bench semantic slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


SCHEMA_VERSION = "frankengate-enterprise-rag-frontier-rerank-v1"
MODEL = "gpt-5.6-luna"
TOKEN_RE = re.compile(r"[A-Za-z0-9_]{3,}")
STOPWORDS = frozenset("a an and are as at be by for from how in is it of on or the their this to what when where which with will within you your".split())
OUTPUT_SCHEMA = {"type": "object", "properties": {"selected_indices": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 19}, "minItems": 1, "maxItems": 10}}, "required": ["selected_indices"], "additionalProperties": False}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def terms(question: str) -> list[str]:
    seen = set()
    result = []
    for term in TOKEN_RE.findall(question.lower()):
        if term in STOPWORDS or term in seen:
            continue
        seen.add(term)
        result.append(term)
    return result


def metrics(ranked: list[str], expected: set[str], candidate_count: int) -> dict[str, float]:
    hits = [index for index, doc_id in enumerate(ranked, start=1) if doc_id in expected]
    return {
        "mrr": 1.0 / hits[0] if hits else 0.0,
        "recall_at_1": float(bool(set(ranked[:1]) & expected)),
        "recall_at_5": float(bool(set(ranked[:5]) & expected)),
        "recall_at_10": float(bool(set(ranked[:10]) & expected)),
    }


def prompt_for(question: str, candidates: list[dict[str, str]]) -> str:
    items = [{"index": index, "doc_id": item["doc_id"], "source_type": item["source_type"], "title": item["title"], "snippet": item["snippet"]} for index, item in enumerate(candidates)]
    return (
        "You are a conservative enterprise evidence selector. Given only the user question and "
        "candidate document previews, select the smallest ordered shortlist of at most 10 candidate "
        "indices that are most likely to contain evidence needed to answer the question. Do not invent "
        "documents, answer the question, or claim that evidence is authoritative. Return JSON only, "
        "matching this schema: " + json.dumps(OUTPUT_SCHEMA, separators=(",", ":")) +
        "\nQUESTION=" + question + "\nCANDIDATES=" + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    )


def call_frontier(prompt: str, raw_path: Path, attempts: int = 2) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-enterprise-rag-") as directory:
        output_path = Path(directory) / "output.json"
        command = ["codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check", "--sandbox", "workspace-write", "--cd", "/private/tmp", "--model", MODEL, "--output-last-message", str(output_path), "-"]
        raw: dict[str, Any] = {"prompt_sha256": stable_hash(prompt), "attempts": []}
        completed = None
        for attempt in range(1, attempts + 1):
            completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=300, cwd="/private/tmp", check=False)
            raw["attempts"].append({"attempt": attempt, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
            if completed.returncode == 0 and output_path.exists():
                break
            if attempt < attempts:
                time.sleep(2 * attempt)
        if completed is None or completed.returncode != 0 or not output_path.exists():
            raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            raise RuntimeError("frontier call failed")
        response = output_path.read_text(encoding="utf-8", errors="replace").strip()
        try:
            value = json.loads(response)
        except json.JSONDecodeError:
            start, end = response.find("{"), response.rfind("}")
            value = json.loads(response[start:end + 1]) if start >= 0 and end > start else None
        raw["structured_output"] = value
        raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    if not isinstance(value, dict) or not isinstance(value.get("selected_indices"), list):
        raise ValueError("invalid structured output")
    indices = [int(item) for item in value["selected_indices"]]
    if not indices or len(indices) > 10 or len(indices) != len(set(indices)) or any(item < 0 or item >= 20 for item in indices):
        raise ValueError("invalid selected indices")
    return value


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    fields = ("mrr", "recall_at_1", "recall_at_5", "recall_at_10")
    return {field: round(sum(float(row[field]) for row in rows) / len(rows), 6) for field in fields} if rows else {}


def run(documents: Path, questions: Path, database: Path, output: Path, raw_dir: Path, candidate_limit: int = 20, reuse_raw: bool = False) -> dict[str, Any]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    question_rows = [row for row in pq.read_table(questions).to_pylist() if row["question_type"] == "semantic"]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    raw_dir.mkdir(parents=True, exist_ok=True)
    for case_index, question in enumerate(question_rows):
        query_terms = terms(question["question"])
        frequencies = {str(row["term"]): int(row["doc"]) for row in connection.execute("SELECT term, doc FROM vocab WHERE term IN (%s)" % ",".join("?" for _ in query_terms), query_terms).fetchall()}
        ranked_terms = sorted((term for term in query_terms if term in frequencies), key=lambda term: (frequencies[term], term))[:8]
        match = " OR ".join(f'"{term}"' for term in (ranked_terms or query_terms[:8]))
        candidates = [dict(row) for row in connection.execute("SELECT doc_id, source_type, title, substr(content, 1, 800) AS snippet FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?", (match, candidate_limit)).fetchall()]
        expected = set(question["expected_doc_ids"] or [])
        lexical_order = [item["doc_id"] for item in candidates[:10]]
        row: dict[str, Any] = {"case_index": case_index, "question_id": question["question_id"], "candidate_count": len(candidates), "expected_count": len(expected), "candidate_recall_at_20": float(bool(set(item["doc_id"] for item in candidates) & expected)), "lexical": metrics(lexical_order, expected, len(candidates))}
        try:
            raw_path = raw_dir / f"case-{case_index:03d}.json"
            value = json.loads(raw_path.read_text(encoding="utf-8"))["structured_output"] if reuse_raw else call_frontier(prompt_for(question["question"], candidates), raw_path)
            selected = [candidates[int(index)]["doc_id"] for index in value["selected_indices"]]
            row["frontier"] = metrics(selected, expected, len(candidates))
        except Exception as exc:
            failures.append({"case_index": case_index, "error": type(exc).__name__})
        rows.append(row)
    connection.close()
    completed = [row for row in rows if "frontier" in row]
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"documents_sha256": sha256(documents), "questions_sha256": sha256(questions), "raw_model_outputs_committed": False},
        "dataset": {"question_type": "semantic", "questions": len(question_rows), "candidate_pool": "top 20 rare-term FTS5 candidates", "candidate_limit": candidate_limit},
        "protocol": {"model": MODEL, "frontier_sees_question": True, "frontier_sees_candidate_titles_and_snippets": True, "frontier_sees_gold_targets": False, "frontier_sees_gold_answers": False, "frontier_calls": len(question_rows), "max_selected": 10},
        "arms": {"lexical_top10": aggregate([row["lexical"] for row in rows]), "frontier_rerank": aggregate([row["frontier"] for row in completed]), "candidate_pool_recall_at_20": round(sum(row["candidate_recall_at_20"] for row in rows) / len(rows), 6) if rows else 0.0},
        "failures": failures,
        "claim_boundary": {"semantic_frontier_reranking_measured": not failures, "dense_embedding_measured": False, "ontology_quality_measured": False, "trace_learning_measured": False, "reason": "Semantic document slice only; frontier can rerank lexical candidates but cannot recover documents absent from the candidate pool."},
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
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--reuse-raw", action="store_true")
    args = parser.parse_args()
    run(args.documents, args.questions, args.database, args.output, args.raw_dir, reuse_raw=args.reuse_raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
