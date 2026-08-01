#!/usr/bin/env python3
"""Audit task-ID overlap between compiler source and replay audit roots.

Raw JSONL remains outside the repository. The committed receipt contains only
file hashes, task-ID hashes, counts, and the overlap verdict, so this can be
used as a leakage gate before interpreting any transfer result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def scan(paths: list[Path]) -> tuple[set[str], list[dict[str, Any]]]:
    task_ids: set[str] = set()
    files: list[dict[str, Any]] = []
    for root in paths:
        for path in sorted(root.resolve(strict=True).glob("*.jsonl")):
            ids: set[str] = set()
            events = 0
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                events += 1
                task_id = row.get("task_id")
                if row.get("event") == "factorial_task_start" and isinstance(task_id, str):
                    ids.add(task_id)
            task_ids.update(ids)
            files.append({
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
                "event_count": events,
                "task_id_hashes": sorted(sha256_text(value) for value in ids),
            })
    return task_ids, files


def run(source_dirs: list[Path], replay_dirs: list[Path]) -> dict[str, Any]:
    source_ids, source_files = scan(source_dirs)
    replay_ids, replay_files = scan(replay_dirs)
    overlap = sorted(source_ids & replay_ids)
    return {
        "schema_version": "frankengate-trace2skill-source-replay-overlap-v1",
        "source": {
            "directories": [str(path.resolve()) for path in source_dirs],
            "files": source_files,
            "task_count": len(source_ids),
            "task_id_hashes": sorted(sha256_text(value) for value in source_ids),
        },
        "replay": {
            "directories": [str(path.resolve()) for path in replay_dirs],
            "files": replay_files,
            "task_count": len(replay_ids),
            "task_id_hashes": sorted(sha256_text(value) for value in replay_ids),
        },
        "overlap_task_count": len(overlap),
        "overlap_task_id_hashes": sorted(sha256_text(value) for value in overlap),
        "contaminated": bool(overlap),
        "claim_boundary": "A zero-overlap receipt is necessary but not sufficient for held-out transfer; it does not establish semantic utility, causal benefit, or promotion eligibility.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, action="append", required=True)
    parser.add_argument("--replay-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = run(args.source_dir, args.replay_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"contaminated": value["contaminated"], "overlap_task_count": value["overlap_task_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
