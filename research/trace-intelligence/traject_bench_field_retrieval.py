#!/usr/bin/env python3
"""Measure field-aware lexical retrieval on public TRAJECT-Bench tools."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from traject_bench_retrieval_baseline import metric_row, rank, tokens, tool_list


SCHEMA_VERSION = "frankengate-traject-bench-field-retrieval-v1"


def nested_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{nested_text(key)} {nested_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(nested_text(item) for item in value)
    return str(value or "")


def fields(tool: dict[str, Any]) -> dict[str, set[str]]:
    return {
        "name": tokens(str(tool.get("tool name", ""))),
        "description": tokens(str(tool.get("tool description", "")) + " " + str(tool.get("parent tool description", ""))),
        "api": tokens(str(tool.get("API name", "")) + " " + str(tool.get("domain name", ""))),
        "schema": tokens(nested_text(tool.get("required_parameters", [])) + " " + nested_text(tool.get("optional_parameters", []))),
        "output": tokens(nested_text(tool.get("output_info", {}))),
        "connected": tokens(nested_text(tool.get("connected tools", []))),
    }


def weighted_score(query_tokens: set[str], field_sets: dict[str, set[str]], weights: dict[str, float]) -> float:
    if not query_tokens:
        return 0.0
    return sum(weight * len(query_tokens & field_sets[field]) / len(query_tokens) for field, weight in weights.items())


def field_rank(query: str, candidates: list[dict[str, Any]], weights: dict[str, float], field_cache: list[dict[str, set[str]]]) -> list[int]:
    query_tokens = tokens(query)
    return sorted(range(len(candidates)), key=lambda index: (-weighted_score(query_tokens, field_cache[index], weights), index))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root: Path, output: Path, *, pool_mode: str = "domain") -> dict[str, Any]:
    files = sorted(root.glob("parallel/*/*.json")) + sorted(root.glob("sequential/*/*.json"))
    all_tools_path = root / "tools" / "all_tools.json"
    all_tools = json.loads(all_tools_path.read_text(encoding="utf-8")) if all_tools_path.exists() else []
    global_tools: list[dict[str, Any]] = []
    if pool_mode == "all":
        seen: set[str] = set()
        for tool in all_tools:
            name = str(tool.get("tool name"))
            if name not in seen:
                seen.add(name)
                global_tools.append(tool)
    tool_files = {path.stem.removesuffix("_tool"): path for path in (root / "tools").glob("*_tool.json")}
    arms = {
        "name": {"name": 1.0},
        "name_description": {"name": 0.5, "description": 0.5},
        "field_aware": {"name": 0.35, "description": 0.2, "api": 0.15, "schema": 0.15, "output": 0.1, "connected": 0.05},
        "identifier_schema": {"name": 0.45, "api": 0.25, "schema": 0.2, "output": 0.1},
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    evaluated = 0
    skipped = 0
    for path in files:
        domain = path.parent.name
        candidates = global_tools if pool_mode == "all" else json.loads(tool_files[domain].read_text(encoding="utf-8")) if domain in tool_files else []
        if not candidates:
            skipped += 1
            continue
        cache = [fields(tool) for tool in candidates]
        for row in json.loads(path.read_text(encoding="utf-8")):
            targets = tool_list(row)
            target_names = {str(item.get("tool name")) for item in targets}
            candidate_names = {str(item.get("tool name")) for item in candidates}
            if not target_names or not target_names <= candidate_names:
                skipped += 1
                continue
            evaluated += 1
            variant = "hard" if "hard" in path.name else "simple" if "simple" in path.name else "unspecified"
            for arm, weights in arms.items():
                if arm == "name":
                    order = rank(str(row.get("query", "")), candidates, include_description=False, candidate_token_sets=[item["name"] for item in cache])
                else:
                    order = field_rank(str(row.get("query", "")), candidates, weights, cache)
                grouped[f"{domain}/{variant}/{arm}"].append(metric_row(row, candidates, order))
    aggregates: dict[str, Any] = {}
    for key, rows in sorted(grouped.items()):
        metric_keys = [name for name, value in rows[0].items() if isinstance(value, (int, float))]
        aggregates[key] = {"records": len(rows), **{name: round(sum(float(row[name]) for row in rows) / len(rows), 6) for name in metric_keys}}
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"root_name": root.name, "file_count": len(files), "data_files_sha256": hashlib.sha256(json.dumps(sorted(file_hash(path) for path in files)).encode()).hexdigest(), "raw_content_committed": False},
        "candidate_pool": {"mode": pool_mode, "global_count": len(global_tools) if pool_mode == "all" else None},
        "arms": arms,
        "records_evaluated": evaluated,
        "skipped": skipped,
        "aggregates": aggregates,
        "claim_boundary": {"field_aware_lexical_measured": True, "embedding_measured": False, "model_quality_measured": False, "enterprise_quality_measured": False, "reason": "Public tool metadata and synthetic target lists; no human labels, production outcomes, or authorization checks."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"records_evaluated": evaluated, "groups": len(aggregates)}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pool", choices=("domain", "all"), default="domain")
    args = parser.parse_args()
    run(args.root, args.output, pool_mode=args.pool)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
