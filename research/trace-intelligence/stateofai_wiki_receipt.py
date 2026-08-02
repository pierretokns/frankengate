#!/usr/bin/env python3
"""Combine State of AI lexical/Tfidf and BGE receipts without raw source text."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generic_rows(path: Path) -> list[dict[str, Any]]:
    result = json.loads(path.read_text(encoding="utf-8"))
    return [{"family": "local", "backend": row["backend"], "compiled": row["compiled"], "size": row["size"], "records": row["records"], "metrics": row["metrics"]} for row in result["results"]]


def dense_rows(path: Path) -> list[dict[str, Any]]:
    result = json.loads(path.read_text(encoding="utf-8"))
    return [{"family": result["model"], "backend": "dense", "compiled": row["compiled"], "size": row["size"], "records": row["records"], "metrics": row["metrics"], "embedding_build_ms": row["embedding_build_ms"], "query_encoding_ms": row["query_encoding_ms"]} for row in result["results"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--generic", type=Path, required=True)
    parser.add_argument("--dense-raw", type=Path, required=True)
    parser.add_argument("--dense-compiled", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "schema_version": "frankengate-stateofai-wiki-receipt-v1",
        "source": {"corpus_sha256": sha256(args.corpus), "corpus_bytes": args.corpus.stat().st_size, "generic_run_sha256": sha256(args.generic), "dense_raw_sha256": sha256(args.dense_raw), "dense_compiled_sha256": sha256(args.dense_compiled)},
        "protocol": {"corpus": "local State of AI wiki export adapted by source domain", "sizes": [1, 5, 10, 25], "k": 20, "gold": "source-record identity from adapted manifest", "answer_quality": False, "frontier_agent": False},
        "aggregate": generic_rows(args.generic) + dense_rows(args.dense_raw) + dense_rows(args.dense_compiled),
        "claim_boundary": "Real local wiki-export retrieval evidence only. Source-title identity labels do not establish answer correctness, enterprise user utility, domain-specific embedding superiority, MCP behavior, or safe NIL handling.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "rows": len(result["aggregate"]), "corpus_sha256": result["source"]["corpus_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
