#!/usr/bin/env python3
"""Compare governed PostgreSQL query behavior before and after ANALYZE.

The input benchmark documents are already content-free.  This module validates
that they are a paired experiment over the same rows, authority denials,
database version, and query set before reporting a statistics-refresh effect.
It does not claim Aurora behavior or production concurrency.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any, Mapping, Optional, Sequence


SCHEMA_VERSION = "frankengate.postgres-planner-statistics-experiment.v1"


class ExperimentError(ValueError):
    """The two benchmark receipts do not support a paired comparison."""


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _result_digest(result: Mapping[str, Any]) -> str:
    body = dict(result)
    body.pop("result_sha256", None)
    return hashlib.sha256(_stable_json(body).encode("utf-8")).hexdigest()


def verify_result(result: Mapping[str, Any]) -> bool:
    digest = result.get("result_sha256")
    return (
        isinstance(digest, str)
        and len(digest) == 64
        and hmac.compare_digest(digest, _result_digest(result))
    )


def _validate_denials(run: Mapping[str, Any], label: str) -> None:
    matrix = run.get("denied_pre_ranking_candidate_matrix")
    if not isinstance(matrix, Mapping) or matrix.get("all_zero") is not True:
        raise ExperimentError(f"{label}: denied candidates are not all zero")
    counts = matrix.get("counts")
    if not isinstance(counts, Mapping):
        raise ExperimentError(f"{label}: denied matrix is missing")
    for scenario, metrics in counts.items():
        if not isinstance(metrics, Mapping):
            raise ExperimentError(f"{label}: denied scenario is invalid")
        if any(
            not isinstance(value, int) or value != 0
            for value in metrics.values()
        ):
            raise ExperimentError(
                f"{label}: denied scenario {scenario} returned a candidate"
            )


def _environment_identity(run: Mapping[str, Any]) -> dict:
    environment = run.get("environment")
    if not isinstance(environment, Mapping):
        raise ExperimentError("environment is missing")
    return {
        key: environment.get(key)
        for key in (
            "database",
            "server_version",
            "vector_extension_version",
            "iterations",
        )
    }


def _plan_signature(plan: Mapping[str, Any]) -> list[dict]:
    if plan.get("predicates_and_literals_emitted") is not False:
        raise ExperimentError("query plans must be redacted")
    nodes = plan.get("nodes")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise ExperimentError("query plan nodes are missing")
    signature = []
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ExperimentError("query plan node is invalid")
        signature.append(
            {
                key: node[key]
                for key in (
                    "depth",
                    "node_type",
                    "join_type",
                    "relation",
                    "index",
                )
                if key in node
            }
        )
    return signature


def _latency_fields(latency: Mapping[str, Any], label: str) -> dict:
    required = ("iterations", "mean_ms", "p50_ms", "p95_ms", "max_ms")
    if any(key not in latency for key in required):
        raise ExperimentError(f"{label}: latency receipt is incomplete")
    result = {}
    for key in required:
        value = latency[key]
        if key == "iterations":
            if not isinstance(value, int) or value <= 0:
                raise ExperimentError(f"{label}: iterations are invalid")
        elif (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
        ):
            raise ExperimentError(f"{label}: latency is invalid")
        result[key] = value
    return result


def compare_runs(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    runtime_receipt: Optional[Mapping[str, str]] = None,
) -> dict:
    """Return a self-verifying, aggregate paired comparison."""

    _validate_denials(before, "before")
    _validate_denials(after, "after")
    before_environment = _environment_identity(before)
    after_environment = _environment_identity(after)
    if before_environment != after_environment:
        raise ExperimentError("environment changed across the pair")
    if before.get("authorized_counts") != after.get("authorized_counts"):
        raise ExperimentError("authorized counts changed across the pair")
    frozen_runtime_receipt = None
    if runtime_receipt is not None:
        image_ref = runtime_receipt.get("image_ref")
        image_digest = runtime_receipt.get("image_digest")
        if not isinstance(image_ref, str) or not image_ref:
            raise ExperimentError("runtime image reference is missing")
        if (
            not isinstance(image_digest, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None
        ):
            raise ExperimentError("runtime image digest is not pinned")
        frozen_runtime_receipt = {
            "image_ref": image_ref,
            "image_digest": image_digest,
        }

    before_latency = before.get("latency")
    after_latency = after.get("latency")
    before_plans = before.get("query_plans")
    after_plans = after.get("query_plans")
    if not all(
        isinstance(value, Mapping)
        for value in (
            before_latency,
            after_latency,
            before_plans,
            after_plans,
        )
    ):
        raise ExperimentError("latency or plan receipts are missing")
    query_names = set(before_latency)
    if (
        query_names != set(after_latency)
        or set(before_plans) != set(after_plans)
    ):
        raise ExperimentError("query sets differ across the pair")
    plan_name_by_query = {
        "personal_history_page": "personal_history",
    }

    queries = {}
    for query_name in sorted(query_names):
        before_values = _latency_fields(
            before_latency[query_name],
            f"before/{query_name}",
        )
        after_values = _latency_fields(
            after_latency[query_name],
            f"after/{query_name}",
        )
        plan_name = plan_name_by_query.get(query_name, query_name)
        before_signature = (
            _plan_signature(before_plans[plan_name])
            if plan_name in before_plans
            else None
        )
        after_signature = (
            _plan_signature(after_plans[plan_name])
            if plan_name in after_plans
            else None
        )
        if (before_signature is None) != (after_signature is None):
            raise ExperimentError(
                f"{query_name}: plan receipt exists in only one run"
            )
        before_p50 = float(before_values["p50_ms"])
        after_p50 = float(after_values["p50_ms"])
        before_p95 = float(before_values["p95_ms"])
        after_p95 = float(after_values["p95_ms"])
        queries[query_name] = {
            "before_iterations": before_values["iterations"],
            "after_iterations": after_values["iterations"],
            "before_mean_ms": before_values["mean_ms"],
            "after_mean_ms": after_values["mean_ms"],
            "before_p50_ms": before_values["p50_ms"],
            "after_p50_ms": after_values["p50_ms"],
            "before_p95_ms": before_values["p95_ms"],
            "after_p95_ms": after_values["p95_ms"],
            "p50_speedup_ratio": (
                round(before_p50 / after_p50, 6)
                if after_p50 > 0
                else None
            ),
            "p95_speedup_ratio": (
                round(before_p95 / after_p95, 6)
                if after_p95 > 0
                else None
            ),
            "plan_signature_changed": (
                before_signature != after_signature
                if before_signature is not None
                else None
            ),
            "before_plan_signature": before_signature,
            "after_plan_signature": after_signature,
        }

    result = {
        "schema_version": SCHEMA_VERSION,
        "paired_unit": "same_database_same_rows_same_authority_queries",
        "intervention": "statistics_refresh",
        "intervention_command_class": "ANALYZE_each_trace_research_table",
        "input_receipts": {
            "before_sha256": hashlib.sha256(
                _stable_json(before).encode("utf-8")
            ).hexdigest(),
            "after_sha256": hashlib.sha256(
                _stable_json(after).encode("utf-8")
            ).hexdigest(),
        },
        "runtime_receipt": frozen_runtime_receipt,
        "environment": before_environment,
        "authorized_counts": copy.deepcopy(before["authorized_counts"]),
        "denied_pre_ranking_candidates_before": 0,
        "denied_pre_ranking_candidates_after": 0,
        "queries": queries,
        "claim_boundary": [
            "This is a single-node local PostgreSQL planner-statistics experiment.",
            "It does not establish Aurora latency, failover, replication, storage, or concurrency behavior.",
            "The paired observation is not an independent-sample causal population estimate.",
            "It demonstrates that freshly bulk-loaded governed trace tables require planner-statistics readiness before latency evaluation.",
        ],
    }
    result["result_sha256"] = _result_digest(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--image-digest", required=True)
    args = parser.parse_args()
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    result = compare_runs(
        before,
        after,
        runtime_receipt={
            "image_ref": args.image_ref,
            "image_digest": args.image_digest,
        },
    )
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        _stable_json(
            {
                "result_sha256": result["result_sha256"],
                "queries": len(result["queries"]),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
