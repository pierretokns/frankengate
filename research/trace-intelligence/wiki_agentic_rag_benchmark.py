#!/usr/bin/env python3
"""Deterministic local benchmark for wiki retrieval backends.

The fixture is intentionally synthetic and enterprise-shaped. It is a protocol
and backend-parity harness, not evidence about Wikipedia or enterprise data.
It exposes the same small contract that a future MCP server must implement:
search, get_page, and expand_links.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from sklearn.feature_extraction.text import TfidfVectorizer


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_./:-]*", re.I)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tokens(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value)]


def fixture(wiki_count: int = 25) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for number in range(wiki_count):
        wiki_id = f"wiki-{number:02d}"
        system = f"Atlas-{number:02d}"
        alias = f"bluebird-{number:02d}"
        region = f"us-east-{(number % 5) + 1}"
        owner = f"team-{(number % 7) + 1}"
        operations_id = f"{wiki_id}/operations"
        overview_id = f"{wiki_id}/overview"
        security_id = f"{wiki_id}/security"
        glossary_id = f"{wiki_id}/glossary"
        pages.extend(
            [
                {
                    "page_id": overview_id,
                    "wiki_id": wiki_id,
                    "title": f"{system} system overview",
                    "aliases": [system, alias, "Atlas"],
                    "text": f"{system} is also called {alias}. The Atlas service is owned by {owner} and runs in {region}. See operations and security.",
                    "links": [operations_id, security_id],
                },
                {
                    "page_id": operations_id,
                    "wiki_id": wiki_id,
                    "title": f"{system} deployment operations",
                    "aliases": [system, alias, "deployment window"],
                    "text": f"{system} deploys every Tuesday from 02:00 to 03:00 UTC in {region}. The preferred endpoint is {system.lower()}.{region}.internal. Rollbacks are owned by {owner}.",
                    "links": [overview_id, security_id],
                },
                {
                    "page_id": security_id,
                    "wiki_id": wiki_id,
                    "title": f"{system} access and security",
                    "aliases": [system, alias, "access policy"],
                    "text": f"{system} requires workforce SSO and a short-lived service token. The {owner} team reviews access quarterly.",
                    "links": [overview_id, glossary_id],
                },
                {
                    "page_id": glossary_id,
                    "wiki_id": wiki_id,
                    "title": f"{system} glossary",
                    "aliases": [system, alias, "Atlas terminology"],
                    "text": f"In {system} documentation, a rollout means a production deployment and a rollback means restoring the previous version.",
                    "links": [overview_id, operations_id],
                },
            ]
        )
        questions.extend(
            [
                {"question_id": f"{wiki_id}-exact", "wiki_id": wiki_id, "slice": "exact_identifier", "question": f"What is the preferred endpoint for {system}?", "gold_page_ids": [operations_id]},
                {"question_id": f"{wiki_id}-semantic", "wiki_id": wiki_id, "slice": "semantic_paraphrase", "question": f"When does {system} normally deploy?", "gold_page_ids": [operations_id]},
                {"question_id": f"{wiki_id}-alias", "wiki_id": wiki_id, "slice": "alias", "question": f"Which team owns {alias} and where does it run?", "gold_page_ids": [overview_id]},
                {"question_id": f"{wiki_id}-cross", "wiki_id": wiki_id, "slice": "cross_wiki_disambiguation", "question": f"For Atlas in {region}, what is the deployment window?", "gold_page_ids": [operations_id]},
            ]
        )
    questions.append(
        {
            "question_id": "nil-nonexistent-system",
            "wiki_id": None,
            "slice": "nil",
            "question": "What is the deployment window for the nonexistent Zeta-99 system?",
            "gold_page_ids": [],
        }
    )
    return {"schema_version": "frankengate-wiki-fixture-v1", "pages": pages, "questions": questions}


class WikiIndex:
    """Backend-neutral retrieval contract used by direct and transport tests."""

    def __init__(self, pages: list[dict[str, Any]], backend: str, compiled: bool = False) -> None:
        if backend not in {"fts", "tfidf", "hybrid"}:
            raise ValueError(f"unsupported backend: {backend}")
        self.pages = pages
        self.backend = backend
        self.compiled = compiled
        self.by_id = {page["page_id"]: page for page in pages}
        self.texts = [self._document_text(page) for page in pages]
        self._vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[\w./:-]+\b", lowercase=True)
        self._matrix = self._vectorizer.fit_transform(self.texts) if pages else None
        self._fts = sqlite3.connect(":memory:")
        self._fts.execute("CREATE VIRTUAL TABLE pages USING fts5(page_id UNINDEXED, wiki_id UNINDEXED, title, body)")
        self._fts.executemany("INSERT INTO pages(page_id,wiki_id,title,body) VALUES(?,?,?,?)", [(p["page_id"], p["wiki_id"], p["title"], text) for p, text in zip(pages, self.texts)])
        self._fts.commit()

    def _document_text(self, page: dict[str, Any]) -> str:
        link_titles = [self.by_id[link]["title"] for link in page.get("links", []) if link in self.by_id]
        compiled = " ".join([page["title"], *page.get("aliases", []), page["text"], *link_titles])
        return compiled if self.compiled else " ".join([page["title"], page["text"]])

    def _fts_scores(self, query: str) -> dict[str, float]:
        terms = tokens(query)
        if not terms:
            return {}
        # OR preserves recall and makes the exact-token control explicit.
        expression = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
        try:
            rows = self._fts.execute("SELECT page_id, bm25(pages) FROM pages WHERE pages MATCH ? ORDER BY bm25(pages)", (expression,)).fetchall()
        except sqlite3.OperationalError:
            return {}
        values = [float(-row[1]) for row in rows]
        maximum = max(values, default=0.0)
        minimum = min(values, default=0.0)
        span = maximum - minimum
        return {row[0]: ((float(-row[1]) - minimum) / span if span else 1.0) for row in rows}

    def _tfidf_scores(self, query: str) -> dict[str, float]:
        if self._matrix is None:
            return {}
        vector = self._vectorizer.transform([query])
        scores = (self._matrix @ vector.T).toarray().ravel()
        return {page["page_id"]: float(score) for page, score in zip(self.pages, scores) if score > 0}

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        lexical = self._fts_scores(query)
        dense = self._tfidf_scores(query)
        if self.backend == "fts":
            scores = lexical
        elif self.backend == "tfidf":
            scores = dense
        else:
            ids = set(lexical) | set(dense)
            scores = {page_id: 0.5 * lexical.get(page_id, 0.0) + 0.5 * dense.get(page_id, 0.0) for page_id in ids}
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
        return [{"page_id": page_id, "wiki_id": self.by_id[page_id]["wiki_id"], "score": score} for page_id, score in ranked]

    def get_page(self, page_id: str) -> dict[str, Any] | None:
        return self.by_id.get(page_id)

    def expand_links(self, page_id: str, depth: int = 1) -> list[dict[str, Any]]:
        seen = {page_id}
        frontier = [page_id]
        result: list[dict[str, Any]] = []
        for _ in range(max(0, depth)):
            next_frontier: list[str] = []
            for current in frontier:
                page = self.by_id.get(current)
                if not page:
                    continue
                for linked in page.get("links", []):
                    if linked not in seen and linked in self.by_id:
                        seen.add(linked)
                        next_frontier.append(linked)
                        result.append(self.by_id[linked])
            frontier = next_frontier
        return result


def reciprocal_rank(ranked: list[dict[str, Any]], gold: set[str]) -> float:
    for index, row in enumerate(ranked, start=1):
        if row["page_id"] in gold:
            return 1.0 / index
    return 0.0


def evaluate(data: dict[str, Any], sizes: Iterable[int], k: int = 5) -> dict[str, Any]:
    all_pages = data["pages"]
    all_wikis = sorted({page["wiki_id"] for page in all_pages})
    all_questions = data["questions"]
    results: list[dict[str, Any]] = []
    for size in sizes:
        selected = set(all_wikis[:size])
        pages = [page for page in all_pages if page["wiki_id"] in selected]
        questions = [question for question in all_questions if not question["gold_page_ids"] or question["wiki_id"] in selected]
        for compiled in (False, True):
            for backend in ("fts", "tfidf", "hybrid"):
                index = WikiIndex(pages, backend=backend, compiled=compiled)
                rows: list[dict[str, Any]] = []
                for question in questions:
                    started = time.perf_counter_ns()
                    ranked = index.search(question["question"], k=k)
                    latency_ms = (time.perf_counter_ns() - started) / 1_000_000
                    gold = set(question["gold_page_ids"])
                    top_ids = {row["page_id"] for row in ranked}
                    nil = not gold
                    rows.append({
                        "question_id": question["question_id"],
                        "slice": question["slice"],
                        "gold_page_ids": sorted(gold),
                        "top_page_ids": [row["page_id"] for row in ranked],
                        "recall_at_1": bool(ranked and ranked[0]["page_id"] in gold) if gold else None,
                        "recall_at_k": bool(top_ids & gold) if gold else None,
                        "mrr": reciprocal_rank(ranked, gold) if gold else None,
                        "wrong_wiki_at_1": bool(ranked and ranked[0]["wiki_id"] != question["wiki_id"]) if ranked and gold else None,
                        "nil_false_positive": bool(ranked) if nil else None,
                        "latency_ms": latency_ms,
                    })
                gold_rows = [row for row in rows if row["gold_page_ids"]]
                nil_rows = [row for row in rows if not row["gold_page_ids"]]
                results.append({
                    "size": size,
                    "backend": backend,
                    "compiled": compiled,
                    "records": len(rows),
                    "metrics": {
                        "recall_at_1": sum(row["recall_at_1"] for row in gold_rows) / len(gold_rows) if gold_rows else 0.0,
                        "recall_at_k": sum(row["recall_at_k"] for row in gold_rows) / len(gold_rows) if gold_rows else 0.0,
                        "mrr": sum(row["mrr"] for row in gold_rows) / len(gold_rows) if gold_rows else 0.0,
                        "wrong_wiki_at_1": sum(row["wrong_wiki_at_1"] for row in gold_rows) / len(gold_rows) if gold_rows else 0.0,
                        "nil_false_positive_rate": sum(row["nil_false_positive"] for row in nil_rows) / len(nil_rows) if nil_rows else 0.0,
                        "p50_latency_ms": percentile([row["latency_ms"] for row in rows], 0.50),
                        "p95_latency_ms": percentile([row["latency_ms"] for row in rows], 0.95),
                    },
                    "per_question": rows,
                })
    return {"schema_version": "frankengate-wiki-agentic-rag-benchmark-v1", "corpus": {"wikis": len(all_wikis), "pages": len(all_pages)}, "results": results}


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate-fixture")
    generate.add_argument("--wikis", type=int, default=25)
    generate.add_argument("--output", type=Path, required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--corpus", type=Path, required=True)
    run.add_argument("--sizes", default="1,5,10,25")
    run.add_argument("--k", type=int, default=5)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate-fixture":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(fixture(args.wikis), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"schema_version": "frankengate-wiki-fixture-v1", "wikis": args.wikis, "output": str(args.output)}, sort_keys=True))
        return 0
    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    sizes = [int(value) for value in args.sizes.split(",") if value.strip()]
    result = evaluate(data, sizes=sizes, k=args.k)
    result["corpus"]["sha256"] = sha256(args.corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "corpus": result["corpus"], "arms": len(result["results"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
