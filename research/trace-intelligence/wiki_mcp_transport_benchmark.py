#!/usr/bin/env python3
"""Measure direct retrieval versus the minimal stdio MCP JSON-RPC boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from wiki_agentic_rag_benchmark import WikiIndex, percentile, sha256


def rpc(process: subprocess.Popen[str], request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n")
    process.stdin.flush()
    return json.loads(process.stdout.readline())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--backend", choices=("fts", "tfidf", "hybrid"), default="hybrid")
    parser.add_argument("--compiled", action="store_true")
    parser.add_argument("--calls", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    index = WikiIndex(data["pages"], backend=args.backend, compiled=args.compiled)
    queries = [question["question"] for question in data["questions"] if question["gold_page_ids"]]
    queries = (queries * ((args.calls // len(queries)) + 1))[: args.calls]
    direct_latencies: list[float] = []
    direct_results: list[list[str]] = []
    for query in queries:
        started = time.perf_counter_ns()
        direct_results.append([row["page_id"] for row in index.search(query, k=5)])
        direct_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("wiki_mcp_server.py")), "--corpus", str(args.corpus), "--backend", args.backend, *( ["--compiled"] if args.compiled else [])], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    transport_latencies: list[float] = []
    transport_results: list[list[str]] = []
    try:
        rpc(process, 1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "benchmark", "version": "0"}})
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}) + "\n")
        process.stdin.flush()
        for request_id, query in enumerate(queries, start=2):
            started = time.perf_counter_ns()
            response = rpc(process, request_id, "tools/call", {"name": "search", "arguments": {"query": query, "k": 5}})
            value = response["result"]["structuredContent"]["value"]
            transport_results.append([row["page_id"] for row in value])
            transport_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
    finally:
        process.terminate()
        process.wait(timeout=5)
    parity = sum(left == right for left, right in zip(direct_results, transport_results)) / len(queries) if queries else 1.0
    result = {
        "schema_version": "frankengate-wiki-mcp-transport-benchmark-v1",
        "protocol": {"backend": args.backend, "compiled": args.compiled, "calls": len(queries), "same_process_backend": True},
        "corpus": {"sha256": sha256(args.corpus), "pages": len(data["pages"])},
        "direct": {"p50_ms": percentile(direct_latencies, 0.50), "p95_ms": percentile(direct_latencies, 0.95)},
        "mcp_stdio_jsonrpc": {"p50_ms": percentile(transport_latencies, 0.50), "p95_ms": percentile(transport_latencies, 0.95)},
        "ranking_parity": parity,
        "claim_boundary": "This measures the local JSON-RPC/MCP-shaped transport boundary with identical retrieval code. It does not measure a frontier model's tool selection, real network MCP, or answer quality.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
