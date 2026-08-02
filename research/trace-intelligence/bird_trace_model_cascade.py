#!/usr/bin/env python3
"""Frontier model-vs-trajectory extraction on public BIRD traces.

The prompt-only arm sees a BIRD question; the trajectory arm additionally sees
the recorded SQL tool call.  The independent SQLite gold-result comparison is
held out from the model and evaluates ``artifact_matches_task``.  Public BIRD
content is used deliberately so no private local history is sent to the
frontier harness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bird_sql_skill_factorial import call_codex
from bird_trace_artifact_reuse import execute, load_tasks, load_trace_candidates


ARMS = ("prompt_only", "trajectory")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_json_response(value: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", value, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    required = {"artifact_matches_task", "replayability", "validator_type", "confidence"}
    return parsed if isinstance(parsed, dict) and required <= set(parsed) else None


def choose_cases(harness_root: Path, per_class: int) -> list[dict[str, Any]]:
    tasks = load_tasks(harness_root)
    candidates = load_trace_candidates(harness_root, tasks)
    grouped: dict[tuple[bool, str], list[dict[str, Any]]] = defaultdict(list)
    for prompt, sql in candidates.items():
        task = tasks[prompt]
        candidate_result = execute(task.db_path, sql)
        gold_result = execute(task.db_path, task.gold_sql)
        if candidate_result is None or gold_result is None:
            continue
        correct = candidate_result == gold_result
        grouped[(correct, task.database)].append({
            "case_hash": sha256_text(f"{task.task_id}:{sql}"),
            "family": task.database,
            "prompt": task.prompt,
            "sql": sql,
            "correct": correct,
        })
    selected: list[dict[str, Any]] = []
    for correct in (True, False):
        families = sorted({family for label, family in grouped if label == correct})
        index = 0
        while sum(item["correct"] == correct for item in selected) < per_class and families:
            family = families[index % len(families)]
            bucket = grouped[(correct, family)]
            if bucket:
                selected.append(bucket.pop(0))
            families = [name for name in families if grouped[(correct, name)]]
            index += 1
    if sum(item["correct"] for item in selected) != per_class or sum(not item["correct"] for item in selected) != per_class:
        raise ValueError("insufficient public BIRD cases in both outcome classes")
    return selected


def prompt_for(case: dict[str, Any], arm: str) -> str:
    context = f"Question:\n{case['prompt']}"
    if arm == "trajectory":
        context += f"\n\nRecorded SQL tool call (public trace):\n{case['sql']}"
    return (
        "Analyze this public text-to-SQL trace. Do not use tools or the network. "
        "Return JSON only with exactly these fields: artifact_matches_task "
        "(true, false, or null), replayability (replayable, not_replayable, or unclear), "
        "validator_type (query_result, tests, process_exit, human_review, or unclear), "
        "confidence (high, medium, or low). Do not invent a hidden gold answer; abstain "
        "when the evidence is insufficient.\n\n" + context
    )


def run(*, harness_root: Path, per_class: int, model: str, workdir: Path, timeout: float, output: Path, raw_output: Path) -> dict[str, Any]:
    cases = choose_cases(harness_root, per_class)
    rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    aggregate: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}
    for case in cases:
        for arm in ARMS:
            response, ok, elapsed_ms = call_codex(prompt_for(case, arm), model, workdir, timeout)
            parsed = parse_json_response(response) if ok else None
            bucket = aggregate[arm]
            bucket["episodes"] += 1
            bucket["valid_json"] += parsed is not None
            bucket["elapsed_ms_total"] += round(elapsed_ms, 3)
            prediction = parsed.get("artifact_matches_task") if parsed else None
            if prediction is True:
                bucket["predicted_true"] += 1
                bucket["correct_true_positive" if case["correct"] else "correct_false_positive"] += 1
            elif prediction is False:
                bucket["predicted_false"] += 1
                bucket["correct_true_negative" if not case["correct"] else "correct_false_negative"] += 1
            else:
                bucket["abstain"] += 1
            if parsed:
                bucket["validator_" + str(parsed.get("validator_type"))] += 1
                bucket["replayability_" + str(parsed.get("replayability"))] += 1
            rows.append({
                "arm": arm,
                "case_hash": case["case_hash"],
                "family": case["family"],
                "gold_correctness_hidden_truth": case["correct"],
                "response_sha256": sha256_text(response),
                "valid_json": parsed is not None,
                "elapsed_ms": round(elapsed_ms, 3),
                "prediction": parsed,
            })
            raw_rows.append({"arm": arm, "case_hash": case["case_hash"], "response": response})
    result = {
        "schema_version": "frankengate-bird-trace-model-cascade-v1",
        "protocol": {"arms": list(ARMS), "per_outcome_class": per_class, "case_count": len(cases), "model": model, "harness": "codex-cli-subscription", "public_dataset": "World Model Harness BIRD-SQL", "gold_hidden_from_model": True, "raw_output": str(raw_output)},
        "summary": {arm: dict(sorted(counter.items())) for arm, counter in aggregate.items()},
        "episodes": rows,
        "claim_boundary": {"public_trace_probe_only": True, "semantic_model_utility_confirmed": False, "automatic_artifact_promotion_authorized": False, "reason": "Paired prompt-only versus recorded-SQL trajectory input on a small public corpus; no human intent labels or changed-system outcomes."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_text(json.dumps(raw_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness-root", type=Path, required=True)
    parser.add_argument("--per-class", type=int, default=8)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path, required=True)
    args = parser.parse_args()
    run(harness_root=args.harness_root, per_class=args.per_class, model=args.model, workdir=args.workdir, timeout=args.timeout, output=args.output, raw_output=args.raw_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
