#!/usr/bin/env python3
"""Bounded frontier reranker comparison on the pinned MATM trace shard.

The benchmark keeps candidate generation fixed and compares lexical ranking,
cached embedding ranking, and a frontier model's pairwise relevance ranking.
The model sees compact query/candidate summaries, never outcome labels or task
IDs. Raw prompts/responses stay in an external directory; the committed
receipt contains only hashes, counts, and aggregate ranking metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow.parquet as parquet

from matm_embedding_similarity_benchmark import lexical_similarity, action_templates, file_sha256


SCHEMA_VERSION = "frankengate-matm-frontier-reranker-benchmark-v1"
DEFAULT_MODEL = "gpt-5.6-luna"
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["scores"],
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["index", "relevance"],
                "properties": {
                    "index": {"type": "integer", "minimum": 0},
                    "relevance": {"type": "integer", "minimum": 0, "maximum": 3},
                },
            },
        }
    },
}


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _work_signature(row: Mapping[str, Any]) -> str:
    return f"{row.get('task_type', '')}|{str(row.get('goal', '')).strip().casefold()}"


def _summary(row: Mapping[str, Any]) -> dict[str, Any]:
    actions = action_templates(row)
    return {
        "task_type": str(row.get("task_type", "")),
        "goal": str(row.get("goal", ""))[:500],
        "action_templates": actions[:10],
        "step_count": len(actions),
    }


def _cosine(matrix: np.ndarray, query: np.ndarray) -> np.ndarray:
    matrix_norm = matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
    query_norm = query / max(float(np.linalg.norm(query)), 1e-12)
    return matrix_norm @ query_norm


def _metrics(orders: Mapping[str, Sequence[int]], relevant: set[int], candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not relevant:
        raise ValueError("query has no relevant candidate")
    result: dict[str, Any] = {}
    for method, order in orders.items():
        positions = [position for position, index in enumerate(order, start=1) if index in relevant]
        result[method] = {
            "mrr": 1.0 / positions[0] if positions else 0.0,
            "recall_at_1": float(any(position <= 1 for position in positions)),
            "recall_at_3": float(any(position <= 3 for position in positions)),
            "recall_at_5": float(any(position <= 5 for position in positions)),
            "top_3_success_rate": (
                sum(bool(candidates[index].get("success")) for index in order[:3])
                / min(3, len(order))
                if order
                else 0.0
            ),
        }
    return result


def _prompt(query: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> str:
    payload = {
        "query": _summary(query),
        "candidates": [{"index": index, "summary": _summary(candidate)} for index, candidate in enumerate(candidates)],
    }
    return (
        "You are ranking prior agent trajectories for a held-out query. "
        "Score each candidate's practical relevance to solving the query, "
        "not writing style. Use 3 for same task/goal, 2 for a closely related "
        "procedure that transfers, 1 for weakly related, and 0 for unrelated "
        "or a likely wrong-task distractor. Do not infer hidden labels. "
        "Return exactly one JSON object matching this schema and include every "
        "candidate index exactly once.\n\n"
        + json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":"))
        + "\n\nDATA:\n"
        + json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    )


def _call_frontier(prompt: str, model: str, timeout_seconds: int, raw_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-matm-reranker-") as directory:
        root = Path(directory)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        command = [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "-s", "read-only", "-m", model,
            "--output-schema", str(schema), "--output-last-message", str(output),
        ]
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            cwd="/private/tmp",
            check=False,
        )
        raw_path.write_text(
            json.dumps(
                {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if completed.returncode != 0 or not output.exists():
            raise RuntimeError(f"frontier call failed: {completed.stderr[-1000:]}")
        value = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("scores"), list):
        raise ValueError("frontier response missing scores")
    return value


def _usage_from_raw(raw_path: Path) -> int | None:
    if not raw_path.exists():
        return None
    text = raw_path.read_text(encoding="utf-8", errors="replace")
    marker = "tokens used"
    position = text.rfind(marker)
    if position < 0:
        return None
    tail = text[position + len(marker):]
    match = __import__("re").search(r"(\d[\d,]*)", tail)
    return int(match.group(1).replace(",", "")) if match else None


def _select_queries(rows: Sequence[Mapping[str, Any]], limit: int) -> list[int]:
    by_model: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        by_model.setdefault(str(row.get("model", "")), []).append(index)
    selected: list[int] = []
    for model in sorted(by_model):
        for index in by_model[model]:
            query = rows[index]
            if any(
                other != index
                and str(rows[other].get("model", "")) != model
                and _work_signature(rows[other]) == _work_signature(query)
                for other in range(len(rows))
            ):
                selected.append(index)
                break
        if len(selected) >= limit:
            break
    return selected[:limit]


def run(
    input_path: Path,
    embedding_path: Path,
    raw_dir: Path,
    *,
    model: str = DEFAULT_MODEL,
    query_limit: int = 12,
    candidate_limit: int = 10,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    observed_sha = file_sha256(input_path)
    table = parquet.read_table(input_path)
    rows = [dict(row) for row in table.to_pylist()]
    if len(rows) != 2130:
        raise ValueError(f"unexpected MATM row count: {len(rows)}")
    vectors = np.load(embedding_path, allow_pickle=False)["vectors"]
    if vectors.shape[0] != len(rows):
        raise ValueError("embedding row count does not match MATM")
    queries = _select_queries(rows, query_limit)
    raw_dir.mkdir(parents=True, exist_ok=True)
    aggregate: dict[str, list[dict[str, Any]]] = {"lexical": [], "embedding": [], "frontier": []}
    failures = 0
    call_receipts: list[dict[str, Any]] = []
    for ordinal, query_index in enumerate(queries):
        query = rows[query_index]
        train_indices = [index for index, row in enumerate(rows) if str(row.get("model")) != str(query.get("model"))]
        relevant_global = {
            index for index in train_indices if _work_signature(rows[index]) == _work_signature(query)
        }
        lexical_scores = sorted(
            ((lexical_similarity(query, rows[index]), index) for index in train_indices),
            reverse=True,
        )
        embedding_scores = sorted(
            ((float(_cosine(vectors[train_indices], vectors[query_index])[position]), index)
             for position, index in enumerate(train_indices)),
            reverse=True,
        )
        candidate_ids: list[int] = []
        for _, index in lexical_scores[:candidate_limit]:
            if index not in candidate_ids:
                candidate_ids.append(index)
        for _, index in embedding_scores[:candidate_limit]:
            if index not in candidate_ids:
                candidate_ids.append(index)
        for index in sorted(relevant_global):
            if index not in candidate_ids:
                candidate_ids.append(index)
        candidate_ids = candidate_ids[: max(candidate_limit, len(relevant_global))]
        candidates = [rows[index] for index in candidate_ids]
        relevant = {position for position, index in enumerate(candidate_ids) if index in relevant_global}
        if not relevant:
            continue
        lexical_order = sorted(range(len(candidates)), key=lambda pos: lexical_similarity(query, candidates[pos]), reverse=True)
        embedding_order = sorted(
            range(len(candidates)),
            key=lambda pos: float(_cosine(vectors[candidate_ids], vectors[query_index])[pos]),
            reverse=True,
        )
        try:
            prompt = _prompt(query, candidates)
            raw_path = raw_dir / f"query-{ordinal:03d}.json"
            call_started = time.perf_counter()
            response = _call_frontier(prompt, model, timeout_seconds, raw_path)
            elapsed_ms = round((time.perf_counter() - call_started) * 1000.0, 3)
            scores = response["scores"]
            by_index = {int(item["index"]): int(item["relevance"]) for item in scores}
            if set(by_index) != set(range(len(candidates))):
                raise ValueError("frontier response did not score every candidate exactly once")
            frontier_order = sorted(range(len(candidates)), key=lambda pos: (by_index[pos], -pos), reverse=True)
            model_status = "ok"
        except Exception as exc:  # bounded benchmark records typed failures
            failures += 1
            call_receipts.append({
                "query": ordinal,
                "status": "error",
                "error": type(exc).__name__,
                "prompt_sha256": _stable_hash(prompt) if "prompt" in locals() else None,
                "raw_sha256": file_sha256(raw_path) if "raw_path" in locals() and raw_path.exists() else None,
            })
            continue
        metrics = _metrics(
            {"lexical": lexical_order, "embedding": embedding_order, "frontier": frontier_order},
            relevant,
            candidates,
        )
        for method, values in metrics.items():
            aggregate[method].append(values)
        call_receipts.append({
            "query": ordinal,
            "status": model_status,
            "candidate_count": len(candidates),
            "elapsed_ms": elapsed_ms,
            "model_tokens_used_diagnostic": _usage_from_raw(raw_path),
            "prompt_sha256": _stable_hash(prompt),
            "raw_sha256": file_sha256(raw_path),
        })
    if not aggregate["frontier"]:
        raise RuntimeError("no frontier query completed")
    summary = {
        method: {
            metric: round(sum(row[metric] for row in values) / len(values), 6)
            for metric in ("mrr", "recall_at_1", "recall_at_3", "recall_at_5", "top_3_success_rate")
        }
        for method, values in aggregate.items()
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"rows": len(rows), "source_sha256": observed_sha, "models": len({str(row.get('model')) for row in rows})},
        "protocol": {
            "query_count_requested": query_limit,
            "query_count_completed": len(aggregate["frontier"]),
            "candidate_limit": candidate_limit,
            "candidate_pool": "union of lexical and cached-embedding top candidates plus all relevant same-signature candidates",
            "relevance_label": "same task_type and normalized goal signature across models",
            "outcomes_hidden_from_frontier": True,
            "raw_model_outputs_external": True,
            "model": model,
        },
        "embedding_cache_sha256": file_sha256(embedding_path),
        "aggregate": summary,
        "frontier_calls": {"requested": len(queries), "completed": len(aggregate["frontier"]), "failures": failures, "receipts": call_receipts},
        "claim_boundary": "Bounded reranking comparison on silver same-work labels. It measures ranking value and cost, not semantic alias truth, changed-agent utility, human insight quality, or skill promotion.",
    }
    result["result_sha256"] = _stable_hash(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--query-limit", type=int, default=12)
    parser.add_argument("--candidate-limit", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        args.input,
        args.embeddings,
        args.raw_dir,
        model=args.model,
        query_limit=args.query_limit,
        candidate_limit=args.candidate_limit,
        timeout_seconds=args.timeout_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "result_sha256": result["result_sha256"], "aggregate": result["aggregate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
