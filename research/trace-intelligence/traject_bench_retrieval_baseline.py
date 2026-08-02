#!/usr/bin/env python3
"""Evaluate deterministic lexical tool retrieval on TRAJECT-Bench.

The benchmark's target tool lists are treated as reference labels. No models,
tool endpoints, or recorded outputs are invoked. The receipt stores hashes and
aggregate ranks only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-lexical-retrieval-v1"
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset("a an and are as at by for from in into is of on or the to with you".split())


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def tokens(value: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(value.casefold()) if token not in STOPWORDS}


def tool_list(row: dict[str, Any]) -> list[dict[str, Any]]:
    value = row.get("tool list", row.get("tool_list", []))
    return value if isinstance(value, list) else []


def score(query: str, tool: dict[str, Any], *, include_description: bool, query_token_set: set[str] | None = None, candidate_token_set: set[str] | None = None) -> float:
    query_tokens = query_token_set if query_token_set is not None else tokens(query)
    if candidate_token_set is None:
        text = str(tool.get("tool name", ""))
        if include_description:
            text += " " + str(tool.get("tool description", ""))
        candidate_token_set = tokens(text)
    candidate_tokens = candidate_token_set
    if not query_tokens or not candidate_tokens:
        return 0.0
    return len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens)


def rank(query: str, candidates: list[dict[str, Any]], *, include_description: bool, candidate_token_sets: list[set[str]] | None = None) -> list[int]:
    query_token_set = tokens(query)
    return sorted(
        range(len(candidates)),
        key=lambda index: (-score(query, candidates[index], include_description=include_description, query_token_set=query_token_set, candidate_token_set=candidate_token_sets[index] if candidate_token_sets is not None else None), index),
    )


def metric_row(row: dict[str, Any], candidates: list[dict[str, Any]], order: list[int]) -> dict[str, Any]:
    target_names = [str(tool.get("tool name")) for tool in tool_list(row)]
    target_set = set(target_names)
    positions = [position for position, index in enumerate(order, start=1) if str(candidates[index].get("tool name")) in target_set]
    target_count = len(target_set)
    first = min(positions) if positions else None
    values: dict[str, Any] = {
        "target_count": target_count,
        "candidate_count": len(candidates),
        "first_target_rank": first,
        "mrr": 1.0 / first if first else 0.0,
    }
    for k in (1, 3, 5, 10, 20):
        values[f"recall_at_{k}"] = len({str(candidates[index].get("tool name")) for index in order[:k]} & target_set) / max(1, target_count)
    top_target = order[:max(1, target_count)]
    values["exact_target_set_at_target_count"] = float({str(candidates[index].get("tool name")) for index in top_target} == target_set)
    return values


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"records": 0}
    metrics = [key for key, value in rows[0].items() if isinstance(value, (float, int))]
    return {"records": len(rows), **{key: round(sum(float(row[key]) for row in rows) / len(rows), 6) for key in metrics}}


def run(root: Path, output: Path, *, pool_mode: str = "domain") -> dict[str, Any]:
    files = sorted(root.glob("parallel/*/*.json")) + sorted(root.glob("sequential/*/*.json"))
    tool_files = {path.stem.removesuffix("_tool"): path for path in sorted((root / "tools").glob("*_tool.json"))}
    all_tools_path = root / "tools" / "all_tools.json"
    all_tools = json.loads(all_tools_path.read_text(encoding="utf-8")) if all_tools_path.exists() else []
    if pool_mode == "all":
        unique: dict[str, dict[str, Any]] = {}
        for item in all_tools:
            if isinstance(item, dict) and str(item.get("tool name")) not in unique:
                unique[str(item.get("tool name"))] = item
        global_candidates = list(unique.values())
    else:
        global_candidates = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_rows: list[dict[str, Any]] = []
    evaluated_records = 0
    skipped = Counter()
    for path in files:
        kind = "sequential" if "/sequential/" in str(path) else "parallel"
        variant = "hard" if "hard" in path.name else "simple" if "simple" in path.name else "unspecified"
        candidates = global_candidates if pool_mode == "all" else json.loads(tool_files[path.parent.name].read_text(encoding="utf-8")) if path.parent.name in tool_files else []
        candidate_token_sets = {
            False: [tokens(str(item.get("tool name", ""))) for item in candidates],
            True: [tokens(str(item.get("tool name", "")) + " " + str(item.get("tool description", ""))) for item in candidates],
        }
        for row in (json.loads(path.read_text(encoding="utf-8")) if path.exists() else []):
            if not isinstance(row, dict):
                continue
            targets = tool_list(row)
            target_names = {str(item.get("tool name")) for item in targets if isinstance(item, dict)}
            candidate_names = {str(item.get("tool name")) for item in candidates if isinstance(item, dict)}
            if not target_names or not target_names <= candidate_names:
                skipped[f"missing_target_{kind}"] += 1
                continue
            evaluated_records += 1
            for arm, include_description in (("name", False), ("name_description", True)):
                values = metric_row(row, candidates, rank(str(row.get("query", "")), candidates, include_description=include_description, candidate_token_sets=candidate_token_sets[include_description]))
                values.update({"arm": arm, "kind": kind, "domain": path.parent.name, "variant": variant})
                grouped[f"{kind}/{variant}/{arm}"].append(values)
                all_rows.append(values)
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"root_name": root.name, "file_count": len(files), "data_files_sha256": stable_hash(sorted(file_sha256(path) for path in files)), "raw_content_committed": False},
        "candidate_pool": {"mode": pool_mode, "global_count": len(global_candidates) if pool_mode == "all" else None, "domain_counts": {domain: {"file": path.name, "count": len(json.loads(path.read_text(encoding="utf-8")))} for domain, path in sorted(tool_files.items())}},
        "records_evaluated": evaluated_records,
        "arm_record_counts": dict(sorted(Counter(row["arm"] for row in all_rows).items())),
        "skipped": dict(sorted(skipped.items())),
        "aggregates": {key: aggregate(values) for key, values in sorted(grouped.items())},
        "claim_boundary": {"lexical_retrieval_measured": True, "embedding_retrieval_measured": False, "model_quality_measured": False, "agent_intervention_measured": False, "enterprise_user_behavior_measured": False, "reason": "Public benchmark reference tool lists and domain pools; no model, tool endpoint, principal, production outcome, or changed-system replay."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"groups": len(grouped), "arm_record_counts": result["arm_record_counts"], "skipped": result["skipped"]}, sort_keys=True))
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
