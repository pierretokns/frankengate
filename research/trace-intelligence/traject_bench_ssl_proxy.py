#!/usr/bin/env python3
"""Run an SSL-shaped representation ablation on TRAJECT-Bench.

This is deliberately a proxy, not a reproduction of the SSL paper.  The
public benchmark has tool metadata and target tool lists, but no grounded
scene graph, authority outcome, or typed resource-effect labels.  We therefore
measure whether deterministic projections of existing fields change candidate
retrieval under the same domain-local pools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from traject_bench_retrieval_baseline import metric_row, tokens, tool_list


SCHEMA_VERSION = "frankengate-traject-bench-ssl-proxy-v1"


def nested_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{nested_text(key)} {nested_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(nested_text(item) for item in value)
    return str(value or "")


def field_sets(tool: dict[str, Any]) -> dict[str, set[str]]:
    """Map available metadata to the three SSL-inspired projections.

    Scheduling approximates the interface/capability fingerprint; structural
    approximates parameter and dependency shape; logical approximates API,
    parameter, and output/effect evidence.  No field is claimed to be a true
    scene or action graph in this public proxy.
    """

    name = str(tool.get("tool name", ""))
    parent = str(tool.get("parent tool name", ""))
    scheduling = tokens(" ".join((name, parent, str(tool.get("API name", "")), str(tool.get("domain name", "")))))
    schema = tokens(
        nested_text(tool.get("required_parameters", []))
        + " "
        + nested_text(tool.get("optional_parameters", []))
    )
    connected = tokens(nested_text(tool.get("connected tools", [])))
    structural = tokens(name) | schema | connected
    logical = tokens(
        " ".join(
            (
                name,
                str(tool.get("API name", "")),
                str(tool.get("domain name", "")),
                nested_text(tool.get("required_parameters", [])),
                nested_text(tool.get("optional_parameters", [])),
                nested_text(tool.get("output_info", {})),
            )
        )
    )
    return {
        "name": tokens(name),
        "scheduling": scheduling,
        "structural": structural,
        "logical": logical,
    }


def weighted_score(query_tokens: set[str], fields: dict[str, set[str]], weights: dict[str, float]) -> float:
    if not query_tokens:
        return 0.0
    return sum(weight * len(query_tokens & fields[field]) / len(query_tokens) for field, weight in weights.items())


def rank(query: str, candidates: list[dict[str, Any]], cache: list[dict[str, set[str]]], weights: dict[str, float]) -> list[int]:
    query_tokens = tokens(query)
    return sorted(
        range(len(candidates)),
        key=lambda index: (-weighted_score(query_tokens, cache[index], weights), index),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root: Path, output: Path) -> dict[str, Any]:
    files = sorted(root.glob("parallel/*/*.json")) + sorted(root.glob("sequential/*/*.json"))
    tool_files = {path.stem.removesuffix("_tool"): path for path in (root / "tools").glob("*_tool.json")}
    arms = {
        "name": {"name": 1.0},
        # SSL-shaped projections.  These weights are fixed before execution.
        "ssl_scheduling": {"scheduling": 1.0},
        "ssl_structural": {"structural": 1.0},
        "ssl_logical": {"logical": 1.0},
        "ssl_rich": {"scheduling": 0.35, "structural": 0.30, "logical": 0.35},
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    evaluated = 0
    skipped = Counter()
    arm_rows: list[dict[str, Any]] = []
    for path in files:
        domain = path.parent.name
        tool_path = tool_files.get(domain)
        if tool_path is None:
            skipped["missing_tool_pool"] += 1
            continue
        candidates = json.loads(tool_path.read_text(encoding="utf-8"))
        candidate_names = {str(item.get("tool name")) for item in candidates}
        cache = [field_sets(item) for item in candidates]
        variant = "hard" if "hard" in path.name else "simple" if "simple" in path.name else "unspecified"
        for row in json.loads(path.read_text(encoding="utf-8")):
            targets = tool_list(row)
            target_names = {str(item.get("tool name")) for item in targets if isinstance(item, dict)}
            if not target_names or not target_names <= candidate_names:
                skipped["missing_target"] += 1
                continue
            evaluated += 1
            for arm, weights in arms.items():
                values = metric_row(row, candidates, rank(str(row.get("query", "")), candidates, cache, weights))
                values.update({"arm": arm, "domain": domain, "variant": variant})
                grouped[f"{domain}/{variant}/{arm}"].append(values)
                arm_rows.append(values)

    def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {"records": 0}
        keys = [key for key, value in rows[0].items() if isinstance(value, (int, float))]
        return {"records": len(rows), **{key: round(sum(float(row[key]) for row in rows) / len(rows), 6) for key in keys}}

    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_name": root.name,
            "file_count": len(files),
            "data_files_sha256": hashlib.sha256(json.dumps(sorted(sha256(path) for path in files)).encode()).hexdigest(),
            "raw_content_committed": False,
        },
        "protocol": {
            "candidate_pool": "domain-local",
            "weights_frozen_before_execution": True,
            "ssl_reproduction": False,
            "field_mapping": {
                "scheduling": "tool/parent name plus API/domain identifiers",
                "structural": "tool name plus parameter shape and connected-tool metadata",
                "logical": "tool/API/domain plus parameter and output metadata",
            },
        },
        "arms": arms,
        "records_evaluated": evaluated,
        "arm_record_counts": dict(sorted(Counter(row["arm"] for row in arm_rows).items())),
        "skipped": dict(sorted(skipped.items())),
        "aggregates": {key: aggregate(rows) for key, rows in sorted(grouped.items())},
        "claim_boundary": {
            "structured_field_retrieval_measured": True,
            "grounded_scene_graph_measured": False,
            "logical_effect_labels_measured": False,
            "enterprise_alias_quality_measured": False,
            "skill_or_artifact_utility_measured": False,
            "reason": "Public target-tool lists and metadata; no principals, authority decisions, replay outcomes, human labels, or changed-system tasks.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"records_evaluated": evaluated, "groups": len(grouped)}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
