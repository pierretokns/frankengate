#!/usr/bin/env python3
"""Build bounded, family-aware public-dataset probes for the HN reimplementation.

The full Oracle corpus/checkpoints are private. This adapter makes the public
transfer tests explicit and reproducible without committing raw corpora:
FiQA uses official BEIR qrels; TechQA uses the Apache-2.0 RAG derivative and
keeps questions with their source technote groups disjoint between train/test.
The runner intentionally samples a bounded candidate corpus, because the
full Climate-FEVER Wikipedia corpus is 5.4M documents and the CPU surrogate is
not a claim of full-corpus reproduction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import zipfile
from pathlib import Path
from typing import Any

from enterprise_hard_negative_mining import run_explicit_split


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bounded_pages(all_pages: list[dict[str, Any]], required: set[str], max_docs: int, seed: int) -> list[dict[str, Any]]:
    required_pages = [page for page in all_pages if str(page["page_id"]) in required]
    others = [page for page in all_pages if str(page["page_id"]) not in required]
    random.Random(seed).shuffle(others)
    selected = required_pages + others[: max(0, max_docs - len(required_pages))]
    return selected


def fiqa(root: Path, max_docs: int, train_limit: int, test_limit: int, seed: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source = root / "fiqa"
    pages_by_id = {str(row["_id"]): {"page_id": str(row["_id"]), "title": row.get("title", ""), "text": row.get("text", ""), "aliases": []} for row in read_jsonl(source / "corpus.jsonl")}
    queries = {str(row["_id"]): row["text"] for row in read_jsonl(source / "queries.jsonl")}

    def read_qrels(path: Path, limit: int) -> list[dict[str, Any]]:
        grouped: dict[str, list[str]] = {}
        with path.open(encoding="utf-8") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                if int(row["score"]) > 0:
                    grouped.setdefault(str(row["query-id"]), []).append(str(row["corpus-id"]))
        rows = []
        for query_id in sorted(grouped):
            if query_id in queries and grouped[query_id]:
                rows.append({"question_id": f"fiqa-{query_id}", "question": queries[query_id], "gold_page_ids": grouped[query_id]})
        return rows[:limit] if limit else rows

    train = read_qrels(source / "qrels" / "train.tsv", train_limit)
    test = read_qrels(source / "qrels" / "test.tsv", test_limit)
    required = {page_id for question in train + test for page_id in question["gold_page_ids"]}
    pages = bounded_pages(list(pages_by_id.values()), required, max_docs, seed)
    data = {"pages": pages, "questions": train + test}
    meta = {"dataset": "FiQA-2018/BEIR", "license": "see upstream BEIR/FiQA terms", "source_hashes": {name: sha256(path) for name, path in (("corpus", source / "corpus.jsonl"), ("queries", source / "queries.jsonl"), ("train_qrels", source / "qrels" / "train.tsv"), ("test_qrels", source / "qrels" / "test.tsv"))}}
    return data, train, test, meta


def techqa(root: Path, max_docs: int, train_limit: int, test_limit: int, seed: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source = root / "techqa-rag-eval"
    rows = json.loads((source / "train.json").read_text(encoding="utf-8"))
    corpus_dir = source / "unpacked" / "corpus"
    all_pages = [{"page_id": path.stem, "title": path.stem, "text": path.read_text(encoding="utf-8", errors="replace"), "aliases": []} for path in sorted(corpus_dir.glob("*.txt"))]
    pages_by_id = {str(page["page_id"]): page for page in all_pages}
    usable = [row for row in rows if not row.get("is_impossible") and row.get("contexts")]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in usable:
        filename = str(row["contexts"][0].get("filename", ""))
        if filename:
            grouped.setdefault(filename.removesuffix(".txt"), []).append(row)
    keys = sorted(grouped)
    split_at = max(1, int(len(keys) * 0.8))
    train_keys, test_keys = keys[:split_at], keys[split_at:]

    def convert(keys: list[str], limit: int) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for key in keys:
            page_id = key if key in pages_by_id else next((candidate for candidate in pages_by_id if candidate == key), None)
            for row in grouped[key]:
                context = row["contexts"][0]
                inferred = str(context.get("filename", "")).removesuffix(".txt")
                output.append({"question_id": f"techqa-{row['id']}", "question": row["question"], "gold_page_ids": [inferred]})
                if limit and len(output) >= limit:
                    return output
        return output

    train = convert(train_keys, train_limit)
    test = convert(test_keys, test_limit)
    required = {page_id for question in train + test for page_id in question["gold_page_ids"]}
    pages = bounded_pages(all_pages, required, max_docs, seed)
    data = {"pages": pages, "questions": train + test}
    meta = {"dataset": "NVIDIA TechQA-RAG-Eval", "license": "Apache-2.0", "source_hashes": {"train": sha256(source / "train.json"), "corpus_zip": sha256(source / "corpus.zip")}}
    return data, train, test, meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=("fiqa", "techqa"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--max-docs", type=int, default=2500)
    parser.add_argument("--max-features", type=int, default=256)
    parser.add_argument("--pca-components", type=int, default=64)
    parser.add_argument("--train-limit", type=int, default=200)
    parser.add_argument("--test-limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.dataset == "fiqa":
        data, train, test, meta = fiqa(args.root, args.max_docs, args.train_limit, args.test_limit, args.seed)
    else:
        data, train, test, meta = techqa(args.root, args.max_docs, args.train_limit, args.test_limit, args.seed)
    result = run_explicit_split(data, train, test, seed=args.seed, split_label="dataset-provided or source-group-disjoint split; bounded candidate corpus", max_features=args.max_features, pca_components=args.pca_components)
    result["dataset"] = meta
    result["corpus"]["candidate_docs"] = len(data["pages"])
    result["corpus"]["train_questions"] = len(train)
    result["corpus"]["test_questions"] = len(test)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"dataset": args.dataset, "metrics": result["metrics"], "train": len(train), "test": len(test)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
