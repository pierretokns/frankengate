#!/usr/bin/env python3
"""Generate a synthetic cohort proving the readiness gate is executable.

The resulting manifest is a protocol self-test only, never empirical enterprise
evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(count: int = 100) -> dict:
    rows = []
    for index in range(count):
        label = "nil" if index < 13 else ("unclear" if index < 25 else "exact")
        rows.append({
            "principal_id": f"principal-{index % 4}",
            "team_id": f"team-{index % 2}",
            "project_id": f"project-{index % 5}",
            "system_id": f"system-{index % 3}",
            "effective_time": f"2026-01-{(index % 28) + 1:02d}",
            "task_id": f"task-{index}",
            "annotator_a_label": label,
            "annotator_b_label": label,
            "changed_environment_id": f"changed-{index % 2}",
            "independent_outcome": "verified" if label == "exact" else "abstained",
            "negative_kind": "same_scope" if index < 50 else None,
        })
    return {"schema": "synthetic-enterprise-replay-selftest-v1", "records": rows, "synthetic_only": True}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--out", type=Path, required=True); args = parser.parse_args(); args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__": main()
