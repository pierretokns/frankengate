#!/usr/bin/env python3
"""Audit whether mined same-domain distractors outrank gold pages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wiki_agentic_rag_benchmark import WikiIndex, sha256


def rank_of(ids: list[str], targets: set[str]) -> int | None:
    return next((index for index, page_id in enumerate(ids, 1) if page_id in targets), None)


def run(data: dict[str, Any], sizes: list[int], k: int) -> dict[str, Any]:
    all_wikis = sorted({page["wiki_id"] for page in data["pages"]})
    arms: list[dict[str, Any]] = []
    for size in sizes:
        selected = set(all_wikis[:size])
        pages = [page for page in data["pages"] if page["wiki_id"] in selected]
        questions = [question for question in data["questions"] if question["gold_page_ids"] and question["wiki_id"] in selected and question.get("hard_negative_page_ids")]
        for compiled in (False, True):
            for backend in ("fts", "tfidf", "hybrid"):
                index = WikiIndex(pages, backend=backend, compiled=compiled)
                rows: list[dict[str, Any]] = []
                for question in questions:
                    ranked = [row["page_id"] for row in index.search(question["question"], k=k)]
                    gold = set(question["gold_page_ids"])
                    hard = set(question["hard_negative_page_ids"])
                    rows.append({
                        "question_id": question["question_id"],
                        "gold_rank": rank_of(ranked, gold),
                        "hard_negative_rank": rank_of(ranked, hard),
                        "hard_negative_at_1": bool(ranked and ranked[0] in hard),
                        "hard_negative_in_k": bool(hard & set(ranked)),
                    })
                arms.append({
                    "size": size,
                    "backend": backend,
                    "compiled": compiled,
                    "records": len(rows),
                    "metrics": {
                        "gold_recall_at_1": sum(row["gold_rank"] == 1 for row in rows) / len(rows) if rows else 0.0,
                        "hard_negative_at_1_rate": sum(row["hard_negative_at_1"] for row in rows) / len(rows) if rows else 0.0,
                        "hard_negative_in_k_rate": sum(row["hard_negative_in_k"] for row in rows) / len(rows) if rows else 0.0,
                        "hard_negative_mean_rank": sum(row["hard_negative_rank"] or (k + 1) for row in rows) / len(rows) if rows else 0.0,
                    },
                })
    return {"schema_version": "frankengate-wiki-hard-negative-audit-v1", "arms": arms, "protocol": {"k": k, "negative_source": "nearest same-domain title-token Jaccard distractor", "labels": "silver metadata-derived"}, "claim_boundary": "This measures distractor exposure, not human semantic difficulty or answer correctness."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--sizes", default="1,5,10")
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    result = run(data, [int(value) for value in args.sizes.split(",") if value.strip()], args.k)
    result["corpus"] = {"sha256": sha256(args.corpus), "pages": len(data["pages"]), "wikis": len({page["wiki_id"] for page in data["pages"]})}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "arms": len(result["arms"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
