#!/usr/bin/env python3
"""Audit typed tool execution and terminal behavior for ToolQA arms."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    transcript = str(row.get("transcript") or "")
    actions = re.findall(r"^Action\s+\d+:\s*(.*)$", transcript, flags=re.MULTILINE)
    observations = re.findall(r"^Observation\s+\d+:\s*(.*)$", transcript, flags=re.MULTILINE)
    finished = bool(re.search(r"^Action\s+\d+:\s*Finish\[", transcript, flags=re.MULTILINE))
    invalid_observations = [
        text for text in observations
        if re.search(r"incorrect|does not exist|filtered due|something wrong|not permitted|failed|error", text, flags=re.I)
    ]
    empty_actions = [action for action in actions if not action.strip()]
    return {
        "instance_id": row.get("instance_id"),
        "steps": int((row.get("meta") or {}).get("n_steps") or len(actions)),
        "finished": finished,
        "halted": bool((row.get("meta") or {}).get("halted")),
        "actions": len(actions),
        "observations": len(observations),
        "invalid_or_error_observations": len(invalid_observations),
        "empty_actions": len(empty_actions),
        "skill_ids_used": list(row.get("skill_ids_used") or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", action="append", nargs=2, metavar=("NAME", "RAW_JSONL"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    arms: dict[str, Any] = {}
    for name, raw_value in args.arm:
        raw_path = Path(raw_value)
        rows = [audit_row(row) for row in load_jsonl(raw_path)]
        arms[name] = {
            "records": len(rows),
            "finished": sum(row["finished"] for row in rows),
            "halted": sum(row["halted"] for row in rows),
            "actions": sum(row["actions"] for row in rows),
            "observations": sum(row["observations"] for row in rows),
            "invalid_or_error_observations": sum(row["invalid_or_error_observations"] for row in rows),
            "empty_actions": sum(row["empty_actions"] for row in rows),
            "avg_steps": (sum(row["steps"] for row in rows) / len(rows)) if rows else 0.0,
            "per_task": rows,
            "raw_sha256": sha256(raw_path),
        }
    result = {
        "schema_version": "frankengate-sra-bench-toolqa-execution-audit-v1",
        "protocol": {
            "typed_fields": ["finished", "halted", "actions", "observations", "invalid_or_error_observations", "empty_actions"],
            "error_rule": "case-insensitive deterministic pattern over Observation text; not a semantic judge",
            "promotion_authorized": False,
        },
        "arms": arms,
        "claim_boundary": "Execution-shape diagnostic only. Error-text counts do not prove tool quality, task failure cause, or skill utility.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({name: {key: value for key, value in arm.items() if key in ("records", "finished", "halted", "actions", "observations", "invalid_or_error_observations", "empty_actions", "avg_steps")} for name, arm in arms.items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
