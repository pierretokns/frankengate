#!/usr/bin/env python3
"""Run frontier adjudication for ToolQA terminal answers.

This is an evaluator, not an agent: the judge sees question, gold answer,
candidate answer, and transcript, and must classify the candidate without
executing tools or changing the benchmark.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "confidence", "evidence", "reason"],
    "properties": {
        "label": {"type": "string", "enum": ["correct_semantic", "format_only", "incorrect", "indeterminate"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "evidence": {"type": "string"},
        "reason": {"type": "string"},
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(raw: str) -> str:
    import re

    matches = re.findall(r"Finish\[([^\]]*)\]", raw)
    return matches[-1].strip() if matches else ""


def prompt(case: dict[str, Any], strict: bool = False) -> str:
    strict_addendum = "\nThis is the skeptical pass: mark incorrect whenever the candidate adds an unrequested interval, omits a required value, gives only a category/label rather than the requested value, or relies on a nonstandard representation that is not explicitly unambiguous. Use correct_semantic sparingly." if strict else ""
    return f"""You are a strict benchmark adjudicator. Do not execute tools, browse, or invent facts. Determine whether the candidate's final answer answers the exact question and agrees with the gold answer.

Use one label:
- correct_semantic: candidate conveys the same answer, including equivalent units/order where unambiguous.
- format_only: candidate is the same answer but differs only in harmless formatting (currency punctuation, 12/24-hour clock, whitespace, etc.).
- incorrect: candidate is wrong, incomplete, refuses despite available evidence, or adds a materially different value.
- indeterminate: the supplied question/transcript/gold do not allow a reliable decision.

Do not call a rounded value correct unless the gold explicitly permits rounding. Do not treat a phrase that merely mentions a requested field as the answer. Return only the requested JSON object.{strict_addendum}

QUESTION:
{case['question']}

GOLD ANSWER:
{case['gold']}

CANDIDATE ANSWER:
{case['predicted']}

TRANSCRIPT (may be truncated):
{case['transcript'][:7000]}
"""


def invoke(case: dict[str, Any], model: str, timeout: int, strict: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-toolqa-judge-") as directory:
        root = Path(directory)
        schema_path, output_path = root / "schema.json", root / "output.json"
        schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")
        completed = subprocess.run(
            ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-s", "read-only", "-m", model, "--output-schema", str(schema_path), "--output-last-message", str(output_path)],
            input=prompt(case, strict=strict), text=True, capture_output=True, timeout=timeout, cwd="/private/tmp", check=False,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr[-2000:])
        result = json.loads(output_path.read_text(encoding="utf-8"))
        result["case_id"] = case["case_id"]
        return result


def build_cases(instances: Path, arms: list[tuple[str, Path, Path]], only_failures: bool) -> list[dict[str, Any]]:
    by_id = {row["instance_id"]: row for row in json.loads(instances.read_text(encoding="utf-8"))}
    cases: list[dict[str, Any]] = []
    for arm_name, raw_path, eval_path in arms:
        eval_rows = {row["instance_id"]: row for row in json.loads(eval_path.read_text(encoding="utf-8"))["details"]}
        for row in (json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line.strip()):
            detail = eval_rows[row["instance_id"]]
            if only_failures and detail["correct"]:
                continue
            instance = by_id[row["instance_id"]]
            cases.append({"case_id": f"{arm_name}:{row['instance_id']}", "arm": arm_name, "instance_id": row["instance_id"], "question": instance["question"], "gold": str(instance["eval_data"]["answer"]), "predicted": extract(str(row.get("raw_output") or "")), "transcript": str(row.get("transcript") or ""), "benchmark_correct": bool(detail["correct"]), "benchmark_match_type": detail.get("match_type")})
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--arm", action="append", nargs=3, metavar=("NAME", "RAW_JSONL", "EVAL_JSON"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--all-records", action="store_true")
    parser.add_argument("--strict-rubric", action="store_true")
    args = parser.parse_args()
    arms = [(name, Path(raw), Path(evaluation)) for name, raw, evaluation in args.arm]
    cases = build_cases(args.instances, arms, only_failures=not args.all_records)
    if args.limit:
        cases = cases[: args.limit]
    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(invoke, case, args.model, args.timeout, args.strict_rubric): case for case in cases}
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            try:
                result = future.result()
                result["arm"] = case["arm"]
                result["instance_id"] = case["instance_id"]
                result["benchmark_correct"] = case["benchmark_correct"]
                result["benchmark_match_type"] = case["benchmark_match_type"]
                results.append(result)
            except Exception as exc:
                failures.append({"case_id": case["case_id"], "error": str(exc)})
    results.sort(key=lambda row: row["case_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": "frankengate-sra-bench-toolqa-semantic-adjudication-raw-v1", "model": args.model, "strict_rubric": args.strict_rubric, "cases_requested": len(cases), "results": results, "failures": failures}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases_requested": len(cases), "results": len(results), "failures": len(failures), "output": str(args.output)}, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
