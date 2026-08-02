#!/usr/bin/env python3
"""Create a content-minimized receipt for the Codex wiki frontier loop."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from wiki_frontier_codex_loop import answer_matches


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    run = json.loads(args.run.read_text(encoding="utf-8"))
    pages = {page["page_id"]: page for page in corpus["pages"]}
    by_size: dict[int, list[dict[str, Any]]] = {}
    for row in run["records"]:
        question = {"slice": row["slice"], "gold_page_ids": row["gold_page_ids"]}
        target = pages.get(row["gold_page_ids"][0]) if row["gold_page_ids"] else None
        corrected = answer_matches(question, row["answer"], target)
        normalized = dict(row)
        normalized["answer_matches_gold_corrected"] = corrected
        by_size.setdefault(int(row["corpus_size"]), []).append(normalized)
    aggregates = []
    for size, rows in sorted(by_size.items()):
        targets = [row for row in rows if row["gold_page_ids"]]
        nils = [row for row in rows if not row["gold_page_ids"]]
        aggregates.append({
            "size": size,
            "records": len(rows),
            "errors": sum(bool(row["error"]) for row in rows),
            "searched_gold": sum(row["searched_gold"] for row in targets) / len(targets) if targets else 0.0,
            "loaded_gold": sum(row["loaded_gold"] for row in targets) / len(targets) if targets else 0.0,
            "finished": sum(row["finished"] for row in rows) / len(rows) if rows else 0.0,
            "target_answer_accuracy": sum(row["answer_matches_gold_corrected"] for row in targets) / len(targets) if targets else 0.0,
            "nil_abstention_accuracy": sum(row["answer_matches_gold_corrected"] for row in nils) / len(nils) if nils else 0.0,
            "avg_steps": sum(row["steps"] for row in rows) / len(rows) if rows else 0.0,
            "p95_latency_ms": sorted(row["latency_ms"] for row in rows)[max(0, int(round((len(rows) - 1) * 0.95)))] if rows else 0.0,
        })
    result = {
        "schema_version": "frankengate-wiki-frontier-codex-receipt-v1",
        "protocol": run["protocol"],
        "corpus": run["corpus"],
        "run_sha256": sha256(args.run),
        "aggregates": aggregates,
        "claim_boundary": "Codex/Luna structured-action frontier loop over a synthetic fixture. Native MCP was not used because non-interactive Codex cancelled custom MCP calls before tools/call dispatch. This is not enterprise transfer or a claim about Claude Code.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "aggregates": aggregates}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
