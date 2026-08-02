#!/usr/bin/env python3
"""Select deterministic held-out ToolQA instances by skill family."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=Path, required=True)
    parser.add_argument("--per-family", type=int, default=2)
    parser.add_argument("--skip", type=int, default=1)
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.instances.read_text(encoding="utf-8"))
    families = sorted({skill for row in rows for skill in row.get("skill_annotations", [])})
    selected = []
    for family in families:
        family_rows = [row for row in rows if family in row.get("skill_annotations", [])]
        selected.extend(family_rows[args.skip : args.skip + args.per_family])
    result = {
        "schema_version": "frankengate-sra-bench-toolqa-cohort-v1",
        "source_sha256": sha256(args.instances),
        "selection": {"families": families, "per_family": args.per_family, "skip": args.skip, "tasks": len(selected)},
        "instances": selected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = selected if args.plain else result
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "tasks": len(selected), "families": families}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
