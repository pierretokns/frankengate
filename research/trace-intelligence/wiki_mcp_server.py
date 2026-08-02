#!/usr/bin/env python3
"""Small stdio MCP server exposing the wiki retrieval contract.

This intentionally implements only the MCP JSON-RPC surface needed by the
benchmark. It keeps the backend identical to ``WikiIndex`` so transport and
retrieval effects can be measured separately.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from wiki_agentic_rag_benchmark import WikiIndex


TOOLS = [
    {
        "name": "search",
        "description": "Search wiki pages and return ranked page IDs with provenance.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "k": {"type": "integer", "minimum": 1, "maximum": 50}}, "required": ["query"]},
    },
    {
        "name": "get_page",
        "description": "Read one page by stable page ID.",
        "inputSchema": {"type": "object", "properties": {"page_id": {"type": "string"}}, "required": ["page_id"]},
    },
    {
        "name": "expand_links",
        "description": "Expand bounded links from a page.",
        "inputSchema": {"type": "object", "properties": {"page_id": {"type": "string"}, "depth": {"type": "integer", "minimum": 1, "maximum": 3}}, "required": ["page_id"]},
    },
]


def reply(request_id: Any, result: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def error(request_id: Any, code: int, message: str) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def call(index: WikiIndex, name: str, arguments: dict[str, Any]) -> Any:
    if name == "search":
        return index.search(str(arguments.get("query", "")), int(arguments.get("k", 5)))
    if name == "get_page":
        return index.get_page(str(arguments.get("page_id", "")))
    if name == "expand_links":
        return index.expand_links(str(arguments.get("page_id", "")), int(arguments.get("depth", 1)))
    raise KeyError(name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--backend", choices=("fts", "tfidf", "hybrid"), default="hybrid")
    parser.add_argument("--compiled", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    index = WikiIndex(data["pages"], backend=args.backend, compiled=args.compiled)
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        request_id = request.get("id")
        method = request.get("method")
        if method == "notifications/initialized":
            continue
        if method == "initialize":
            reply(request_id, {"protocolVersion": request.get("params", {}).get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "frankengate-wiki", "version": "0.1.0"}})
            continue
        if method == "ping":
            reply(request_id, {})
            continue
        if method == "tools/list":
            reply(request_id, {"tools": TOOLS})
            continue
        if method == "tools/call":
            params = request.get("params", {})
            try:
                value = call(index, str(params.get("name")), dict(params.get("arguments") or {}))
            except (KeyError, TypeError, ValueError) as exc:
                error(request_id, -32602, str(exc))
                continue
            text = json.dumps(value, separators=(",", ":"))
            reply(request_id, {"content": [{"type": "text", "text": text}], "structuredContent": {"value": value}, "isError": False})
            continue
        if request_id is not None:
            error(request_id, -32601, f"method not found: {method}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
