#!/usr/bin/env python3
"""Mine reusable failure signatures from Recovery-Bench trajectories.

The receipt is content-free: trajectory text, commands, prompts, and task
names never leave the local process. This measures signal concentration only;
it does not claim that a repeated signature is a causal recovery skill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "frankengate-recovery-bench-failure-signals-v1"
ERROR_PATTERNS = {
    "error": re.compile(r"\berror\b|\bfailed\b|\bfailure\b", re.I),
    "traceback": re.compile(r"traceback|stack trace", re.I),
    "missing_resource": re.compile(r"no such file|not found|does not exist", re.I),
    "timeout": re.compile(r"timeout|timed out|time limit", re.I),
    "permission": re.compile(r"permission denied|not permitted|forbidden", re.I),
    "parse": re.compile(r"json decode|parse error|invalid json|malformed", re.I),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _tool_family(name: str) -> str:
    lowered = name.lower()
    if "bash" in lowered or "shell" in lowered or "command" in lowered:
        return "shell"
    if "python" in lowered:
        return "python"
    if "file" in lowered or "read" in lowered or "write" in lowered:
        return "file"
    if not lowered:
        return "unknown"
    return "other"


def summarize_trajectory(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    steps = value.get("steps") if isinstance(value, dict) and isinstance(value.get("steps"), list) else []
    counts = Counter({key: 0 for key in ERROR_PATTERNS})
    families: Counter[str] = Counter()
    tool_calls = 0
    observation_events = 0
    task_complete = False
    for step in steps:
        if not isinstance(step, dict):
            continue
        calls = step.get("tool_calls") if isinstance(step.get("tool_calls"), list) else []
        tool_calls += len(calls)
        for call in calls:
            if isinstance(call, dict):
                function = call.get("function_name") or call.get("name") or ""
                families[_tool_family(str(function))] += 1
        observation = step.get("observation")
        if observation is not None:
            observation_events += 1
            text = json.dumps(observation, ensure_ascii=False, sort_keys=True)
            for key, pattern in ERROR_PATTERNS.items():
                counts[key] += len(pattern.findall(text))
        message = step.get("message")
        if isinstance(message, str) and re.search(r'"task_complete"\s*:\s*true', message):
            task_complete = True
    dominant_family = families.most_common(1)[0][0] if families else "none"
    feature = {
        "step_bucket": min(5, len(steps) // 10),
        "tool_bucket": min(5, tool_calls // 10),
        "observation_bucket": min(5, observation_events // 10),
        "dominant_tool_family": dominant_family,
        "error_flags": tuple(sorted(key for key, count in counts.items() if count)),
        "task_complete": task_complete,
    }
    score = (
        counts["error"]
        + 2 * counts["traceback"]
        + counts["missing_resource"]
        + 2 * counts["timeout"]
        + counts["permission"]
        + 2 * counts["parse"]
    )
    return {
        "steps": len(steps),
        "tool_calls": tool_calls,
        "observation_events": observation_events,
        "signal_counts": dict(sorted(counts.items())),
        "tool_families": dict(sorted(families.items())),
        "task_complete": task_complete,
        "feature": feature,
        "signature": _stable_hash(feature)[:16],
        "signal_score": score,
    }


def _selection_metrics(rows: list[dict[str, Any]], selected: list[int], mode_counts: Counter[str]) -> dict[str, Any]:
    if not selected:
        return {"selected": 0, "repeat_mode_rate": 0.0, "support3_mode_rate": 0.0, "unique_modes": 0}
    repeat = sum(mode_counts[rows[index]["signature"]] >= 2 for index in selected)
    support3 = sum(mode_counts[rows[index]["signature"]] >= 3 for index in selected)
    return {
        "selected": len(selected),
        "repeat_mode_rate": round(repeat / len(selected), 6),
        "support3_mode_rate": round(support3 / len(selected), 6),
        "unique_modes": len({rows[index]["signature"] for index in selected}),
    }


def run(*, manifest: Path, runs_root: Path, output: Path) -> dict[str, Any]:
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    entries = manifest_value.get("failures", [])
    rows: list[dict[str, Any]] = []
    missing_trajectories = 0
    for entry in entries:
        relative = entry.get("trajectory") if isinstance(entry, dict) else None
        if not relative:
            missing_trajectories += 1
            continue
        path = runs_root / relative
        if not path.is_file():
            missing_trajectories += 1
            continue
        try:
            rows.append(summarize_trajectory(path))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            missing_trajectories += 1
    mode_counts = Counter(row["signature"] for row in rows)
    k = max(1, len(rows) // 4) if rows else 0
    signal_order = sorted(range(len(rows)), key=lambda index: (-rows[index]["signal_score"], -rows[index]["steps"], rows[index]["signature"]))
    length_order = sorted(range(len(rows)), key=lambda index: (-rows[index]["steps"], rows[index]["signature"]))
    random_metrics = []
    for seed in range(32):
        order = sorted(range(len(rows)), key=lambda index: hashlib.sha256(f"{seed}:{index}".encode()).hexdigest())
        random_metrics.append(_selection_metrics(rows, order[:k], mode_counts))
    result = {
        "schema": SCHEMA,
        "source": {
            "manifest_sha256": _sha256(manifest),
            "trajectory_count": len(rows),
            "missing_trajectory_count": missing_trajectories,
            "raw_content_committed": False,
        },
        "signature_population": {
            "unique_signatures": len(mode_counts),
            "repeated_signatures": sum(count >= 2 for count in mode_counts.values()),
            "support3_signatures": sum(count >= 3 for count in mode_counts.values()),
            "max_signature_support": max(mode_counts.values(), default=0),
        },
        "selection": {
            "selection_fraction": 0.25,
            "k": k,
            "signal": _selection_metrics(rows, signal_order[:k], mode_counts),
            "length": _selection_metrics(rows, length_order[:k], mode_counts),
            "random_mean": {
                key: round(sum(item[key] for item in random_metrics) / len(random_metrics), 6)
                for key in ("repeat_mode_rate", "support3_mode_rate", "unique_modes")
            }
            if random_metrics
            else {},
        },
        "signal_totals": {
            key: sum(row["signal_counts"][key] for row in rows)
            for key in sorted(ERROR_PATTERNS)
        },
        "claim_boundary": {
            "repeated_failure_modes_detected": bool(mode_counts),
            "reusable_recovery_skill_confirmed": False,
            "recovery_outcome_measured": False,
            "reason": "Cheap structural signals are evaluated only for triage concentration; repeated signatures are not proof of causal repair utility or skill transfer.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["selection"], sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(manifest=args.manifest.resolve(), runs_root=args.runs_root.resolve(), output=args.output.resolve())


if __name__ == "__main__":
    main()
