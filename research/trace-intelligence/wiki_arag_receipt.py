#!/usr/bin/env python3
"""Create a content-minimized receipt for the A-RAG frontier run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_size: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_size.setdefault(int(row["corpus_size"]), []).append(row)
    result: list[dict[str, Any]] = []
    for size, group in sorted(by_size.items()):
        targets = [row for row in group if row["gold_page_ids"]]
        nils = [row for row in group if not row["gold_page_ids"]]
        tool_counts: dict[str, int] = {}
        for row in group:
            for tool, count in row.get("tool_counts", {}).items():
                tool_counts[tool] = tool_counts.get(tool, 0) + count
        latencies = sorted(float(row["latency_ms"]) for row in group)
        p95 = latencies[max(0, int(round((len(latencies) - 1) * 0.95)))] if latencies else 0.0
        result.append(
            {
                "size": size,
                "records": len(group),
                "errors": sum(bool(row["error"]) for row in group),
                "searched_gold": sum(row["searched_gold"] for row in targets) / len(targets) if targets else 0.0,
                "loaded_gold": sum(row["loaded_gold"] for row in targets) / len(targets) if targets else 0.0,
                "finished": sum(row["finished"] for row in group) / len(group) if group else 0.0,
                "target_answer_accuracy": sum(row["answer_matches_gold"] for row in targets) / len(targets) if targets else 0.0,
                "nil_abstention_accuracy": sum(row["answer_matches_gold"] for row in nils) / len(nils) if nils else 0.0,
                "avg_steps": sum(row["steps"] for row in group) / len(group) if group else 0.0,
                "p95_latency_ms": p95,
                "tool_counts": tool_counts,
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = json.loads(args.run.read_text(encoding="utf-8"))
    result = {
        "schema_version": "frankengate-wiki-arag-codex-receipt-v1",
        "protocol": run["protocol"],
        "corpus": run["corpus"],
        "run_sha256": sha256(args.run),
        "aggregates": aggregate(run["records"]),
        "claim_boundary": "A-RAG-style hierarchical tool-choice frontier loop over a synthetic fixture. Native MCP was not used; this is not evidence of enterprise transfer or a claim about Claude Code.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "aggregates": result["aggregates"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
