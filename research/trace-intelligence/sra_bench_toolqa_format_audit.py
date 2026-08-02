#!/usr/bin/env python3
"""Audit ToolQA terminal results under conservative numeric/time formatting equivalence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import string
from decimal import Decimal
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def extract(raw: str) -> str:
    matches = re.findall(r"Finish\[([^\]]*)\]", raw)
    return matches[-1].strip() if matches else ""


def benchmark_normalize(value: str) -> str:
    value = "".join(ch for ch in value.lower() if ch not in string.punctuation)
    value = re.sub(r"\b(a|an|the|usd)\b", " ", value)
    return " ".join(value.split())


def parse_number(value: str) -> Decimal | None:
    text = value.lower().replace("usd", "").replace("$", "").replace(",", "").strip()
    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def parse_time(value: str) -> int | None:
    text = value.lower().strip().replace(".", "")
    match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*([ap]m)?", text)
    if match:
        hour, minute, suffix = int(match.group(1)), int(match.group(2)), match.group(3)
        if suffix:
            if hour == 12:
                hour = 0
            if suffix == "pm":
                hour += 12
        return hour * 60 + minute if hour < 24 and minute < 60 else None
    match = re.fullmatch(r"(\d{3,4})(?:\.0+)?", text)
    if match:
        value = int(match.group(1))
        hour, minute = value // 100, value % 100
        return hour * 60 + minute if hour < 24 and minute < 60 else None
    return None


def format_equivalence(gold: str, predicted: str) -> str | None:
    if benchmark_normalize(gold) == benchmark_normalize(predicted):
        return None
    gold_number, predicted_number = parse_number(gold), parse_number(predicted)
    if gold_number is not None and predicted_number is not None and gold_number == predicted_number:
        return "numeric_format"
    gold_time, predicted_time = parse_time(gold), parse_time(predicted)
    if gold_time is not None and predicted_time is not None and gold_time == predicted_time:
        return "time_format"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--external-zip", type=Path, required=True)
    parser.add_argument("--arm", action="append", nargs=3, metavar=("NAME", "RAW_JSONL", "EVAL_JSON"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    instances = json.loads(args.instances.read_text(encoding="utf-8"))
    by_id = {row["instance_id"]: row for row in instances}
    arms: dict[str, Any] = {}
    for name, raw_value, eval_value in args.arm:
        raw_path, eval_path = Path(raw_value), Path(eval_value)
        rows = load_jsonl(raw_path)
        eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
        recoveries = []
        for row in rows:
            gold = str(by_id[row["instance_id"]]["eval_data"]["answer"])
            predicted = extract(str(row.get("raw_output") or ""))
            kind = format_equivalence(gold, predicted)
            if kind:
                recoveries.append({"instance_id": row["instance_id"], "kind": kind, "gold": gold, "predicted": predicted})
        strict_correct = int(eval_data["metrics"]["correct"])
        arms[name] = {
            "records": len(rows),
            "strict_metrics": eval_data["metrics"],
            "format_recoveries": recoveries,
            "format_recovered_correct": strict_correct + len(recoveries),
            "raw_sha256": sha256(raw_path),
            "evaluation_sha256": sha256(eval_path),
        }
    result = {
        "schema_version": "frankengate-sra-bench-toolqa-format-audit-v1",
        "dataset": {"name": "toolqa", "tasks": len(instances), "instances_sha256": sha256(args.instances), "external_corpus_zip_sha256": sha256(args.external_zip)},
        "protocol": {"format_rules": ["exact ToolQA normalization first", "currency/number punctuation and USD removal with exact Decimal equality", "24-hour/12-hour/time-like numeric equivalence"], "semantic_inference": False, "promotion_authorized": False},
        "arms": arms,
        "claim_boundary": "Conservative deterministic formatting audit over the completed 14-task public ToolQA arms. Recovered cases are not semantic or terminal-outcome labels; no enterprise transfer or skill-promotion claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "arms": {name: {"strict": arm["strict_metrics"], "format_recovered_correct": arm["format_recovered_correct"], "recoveries": arm["format_recoveries"]} for name, arm in arms.items()}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
