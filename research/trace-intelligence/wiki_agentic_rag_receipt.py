#!/usr/bin/env python3
"""Reduce a local wiki benchmark run to a reviewable aggregate receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = json.loads(args.run.read_text(encoding="utf-8"))
    aggregate: list[dict[str, Any]] = []
    for row in run["results"]:
        aggregate.append({"size": row["size"], "backend": row["backend"], "compiled": row["compiled"], "records": row["records"], "metrics": row["metrics"]})
    result = {
        "schema_version": "frankengate-wiki-agentic-rag-receipt-v1",
        "protocol": {
            "corpus_kind": "synthetic enterprise-shaped fixture",
            "wikis": [1, 5, 10, 25],
            "backends": ["fts", "tfidf", "hybrid"],
            "representations": ["raw", "compiled"],
            "contract": ["search", "get_page", "expand_links"],
            "frontier_agent_run": False,
            "mcp_wire_protocol_run": False,
        },
        "fixture": {"sha256": sha256(args.fixture), "bytes": args.fixture.stat().st_size},
        "run": {"sha256": sha256(args.run), "bytes": args.run.stat().st_size},
        "corpus": run["corpus"],
        "aggregate": aggregate,
        "claim_boundary": "Local backend-parity and scale smoke test only. The fixture is synthetic; these results do not establish Wikipedia quality, MCP behavior, frontier-agent answer quality, or enterprise transfer.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "fixture": result["fixture"], "arms": len(aggregate)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
