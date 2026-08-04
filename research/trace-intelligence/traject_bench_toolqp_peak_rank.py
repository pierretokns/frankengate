#!/usr/bin/env python3
"""Apply ToolQP's peak-rank aggregation to an existing query-planning receipt.

This is an inference-stage reproduction only. It reuses the public TRAJECT
cases and externally stored planner outputs from the bounded query-planning
probe; it does not reproduce ToolQP's SFT/RLVR training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from traject_bench_frontier_reranker import metrics
from traject_bench_query_planning_probe import diverse_cases, planned_rank
from traject_bench_retrieval_baseline import rank, tokens, tool_list


SCHEMA_VERSION = "frankengate-traject-bench-toolqp-peak-rank-v1"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peak_rank(queries: list[str], candidates: list[dict[str, Any]], *, top_k: int = 5) -> list[int]:
    """Rank by the best (lowest) rank observed in any retrieval turn."""
    best: dict[int, tuple[int, int]] = {}
    for turn, query in enumerate(queries):
        order = rank(
            query,
            candidates,
            include_description=False,
            candidate_token_sets=[tokens(str(item.get("tool name", ""))) for item in candidates],
        )
        for position, index in enumerate(order[:top_k], start=1):
            best[index] = min(best.get(index, (10**9, 10**9)), (position, turn))
    return sorted(range(len(candidates)), key=lambda index: (best.get(index, (10**9, 10**9)), index))


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"records": 0}
    metrics_keys = ("mrr", "recall_at_1", "recall_at_5", "recall_at_10", "candidate_coverage")
    return {"records": len(rows), **{key: round(sum(float(row[key]) for row in rows) / len(rows), 6) for key in metrics_keys}}


def run(root: Path, raw_dir: Path, output: Path, *, limit: int = 8, top_k: int = 5) -> dict[str, Any]:
    cases = diverse_cases(root, limit)
    if len(cases) != limit:
        raise ValueError(f"expected {limit} selected cases, got {len(cases)}")
    rows: list[dict[str, Any]] = []
    raw_receipts: list[dict[str, Any]] = []
    for index, (case_id, row, _initial) in enumerate(cases):
        raw_path = raw_dir / f"case-{index:03d}.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        queries = raw.get("structured_output", {}).get("queries")
        if not isinstance(queries, list) or len(queries) != 3 or not all(isinstance(value, str) for value in queries):
            raise ValueError(f"invalid planner receipt for case {index}")
        domain = case_id.split("/", 1)[0]
        candidates = json.loads((root / "tools" / f"{domain}_tool.json").read_text(encoding="utf-8"))
        query_sequence = [str(row.get("query", ""))] + [str(value) for value in queries]
        baseline = rank(
            query_sequence[0],
            candidates,
            include_description=False,
            candidate_token_sets=[tokens(str(item.get("tool name", ""))) for item in candidates],
        )
        union, _ = planned_rank(query_sequence, candidates)
        peak = peak_rank(query_sequence, candidates, top_k=top_k)
        target_names = {str(item.get("tool name")) for item in tool_list(row)}
        values = {}
        for arm, order in (("baseline", baseline), ("union", union), ("peak_rank", peak)):
            value = metrics(row, candidates, order)
            value["candidate_coverage"] = len({str(candidates[i].get("tool name")) for i in order[:16]} & target_names) / max(1, len(target_names))
            values[arm] = value
        rows.append({"case_id": case_id, "target_count": len(target_names), **values})
        raw_receipts.append({"case_index": index, "raw_sha256": file_hash(raw_path)})
    arms = {arm: aggregate([row[arm] for row in rows]) for arm in ("baseline", "union", "peak_rank")}
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"root_name": root.name, "selected_cases": len(cases), "raw_content_committed": False},
        "protocol": {
            "planner_outputs_reused": True,
            "planner_training_reproduced": False,
            "retriever": "domain-scoped name-token Jaccard",
            "feedback_top_k": top_k,
            "aggregation": "peak rank: lowest rank observed across original query and three planner queries",
            "planner_sees_gold_targets": False,
            "planner_sees_tool_outputs": False,
        },
        "arms": arms,
        "rows": [{"case_id": row["case_id"], **{arm: row[arm] for arm in ("baseline", "union", "peak_rank")}} for row in rows],
        "raw_receipts": raw_receipts,
        "claim_boundary": {"peak_rank_aggregation_measured": True, "toolqp_training_reproduced": False, "enterprise_artifact_utility_measured": False, "automatic_acceptance_authorized": False},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["arms"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    run(args.root, args.raw_dir, args.output, limit=args.limit, top_k=args.top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
