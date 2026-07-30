"""Execute AgentEvals through its installed public configuration and runner APIs."""

from __future__ import annotations

import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

from agentevals.config import BuiltinMetricDef, EvalRunConfig
from agentevals.resolvers import reset_resolved_credentials, set_resolved_credentials
from agentevals.runner import run_evaluation


async def _run_one(
    *,
    trace_path: str,
    eval_set_path: str,
    match_type: str,
) -> dict[str, Any]:
    config = EvalRunConfig(
        trace_files=[trace_path],
        eval_set_file=eval_set_path,
        trace_format="otlp-json",
        output_format="json",
        evaluators=[
            BuiltinMetricDef(
                name="tool_trajectory_avg_score",
                threshold=0.5,
                trajectory_match_type=match_type,
            )
        ],
        max_concurrent_traces=1,
        max_concurrent_evals=1,
    )
    try:
        result = await asyncio.wait_for(run_evaluation(config), timeout=30)
    except TimeoutError:
        return {
            "score": None,
            "status": "ERRORED",
            "error_type": "timeout",
        }
    if result.errors:
        return {
            "score": None,
            "status": "ERRORED",
            "error_type": "run_error",
        }
    if len(result.trace_results) != 1:
        return {
            "score": None,
            "status": "ERRORED",
            "error_type": "unexpected_trace_count",
        }
    metric_results = result.trace_results[0].metric_results
    if len(metric_results) != 1:
        return {
            "score": None,
            "status": "ERRORED",
            "error_type": "unexpected_metric_count",
        }
    metric = metric_results[0]
    return {
        "score": metric.score,
        "status": metric.eval_status or "ERRORED",
        "error_type": type(metric.error).__name__ if metric.error else None,
    }


async def _run_semantic(
    *,
    trace_path: str,
    eval_set_path: str,
    judge_model: str,
    judge_base_url: str,
) -> dict[str, Any]:
    config = EvalRunConfig(
        trace_files=[trace_path],
        eval_set_file=eval_set_path,
        trace_format="otlp-json",
        output_format="json",
        evaluators=[
            BuiltinMetricDef(
                name="final_response_match_v2",
                threshold=0.5,
                judge_model=judge_model,
                credential_ref="local-judge",
                judge_base_url=judge_base_url,
            )
        ],
        max_concurrent_traces=1,
        max_concurrent_evals=1,
    )
    try:
        result = await asyncio.wait_for(run_evaluation(config), timeout=90)
    except TimeoutError:
        return {
            "score": None,
            "status": "ERRORED",
            "error_type": "timeout",
        }
    if result.errors or len(result.trace_results) != 1:
        return {
            "score": None,
            "status": "ERRORED",
            "error_type": "run_error",
        }
    metric_results = result.trace_results[0].metric_results
    if len(metric_results) != 1:
        return {
            "score": None,
            "status": "ERRORED",
            "error_type": "unexpected_metric_count",
        }
    metric = metric_results[0]
    return {
        "score": metric.score,
        "status": metric.eval_status or "ERRORED",
        "error_type": "metric_error" if metric.error else None,
    }


async def execute(spec: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    credential_token = None
    semantic = spec.get("semantic")
    if semantic:
        import os

        api_key = os.environ.get("FRANKENGATE_AGENT_EVALS_JUDGE_KEY")
        if not api_key:
            raise ValueError("semantic run requires the scoped judge credential")
        credential_token = set_resolved_credentials({"local-judge": api_key})
    try:
        for item in spec["items"]:
            for match_type in spec["match_types"]:
                result = await _run_one(
                    trace_path=item["trace_path"],
                    eval_set_path=item["eval_set_path"],
                    match_type=match_type,
                )
                rows.append(
                    {
                        "case_id": item["case_id"],
                        "arm": item["arm"],
                        "assertion": match_type,
                        **result,
                    }
                )
            if semantic and item["arm"] in semantic["arms"]:
                result = await _run_semantic(
                    trace_path=item["trace_path"],
                    eval_set_path=item["eval_set_path"],
                    judge_model=semantic["judge_model"],
                    judge_base_url=semantic["judge_base_url"],
                )
                semantic_rows.append(
                    {
                        "case_id": item["case_id"],
                        "arm": item["arm"],
                        "assertion": "final_response_match_v2",
                        **result,
                    }
                )
    finally:
        if credential_token is not None:
            reset_resolved_credentials(credential_token)
    return {
        "driver_schema": "frankengate-agentevals-upstream-raw-v1",
        "package_version": version("agentevals-cli"),
        "python_version": __import__("platform").python_version(),
        "rows": rows,
        "semantic_rows": semantic_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    result = asyncio.run(execute(spec))
    args.output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
