#!/usr/bin/env python3
"""Measure LRAT-style exposed-but-unbrowsed candidate availability.

This is a deterministic schema audit over the ten public LRAT sample
trajectories. It does not call the LRAT judge or treat unexposed documents as
negatives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-lrat-exposure-negative-audit-v1"
DOC_ID = re.compile(r"(?:DocID|docid)\s*[:=]\s*[\"']?([A-Za-z0-9_.:-]+)")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_ids(value: Any) -> set[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None and parsed != value:
            return parse_ids(parsed)
        return set(DOC_ID.findall(value))
    if isinstance(value, list):
        return {str(item) for item in value if isinstance(item, (str, int))}
    if isinstance(value, dict):
        result: set[str] = set()
        for key, item in value.items():
            if str(key).lower() in {"docid", "docids", "document_id", "document_ids"}:
                if isinstance(item, (str, int)):
                    result.add(str(item))
                else:
                    result.update(parse_ids(item))
            else:
                result.update(parse_ids(item))
        return result
    return set()


def audit(paths: list[Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    for path in sorted(paths):
        source_hashes[path.name] = file_hash(path)
        trajectory = json.loads(path.read_text(encoding="utf-8"))
        exposed: set[str] = set()
        browsed: set[str] = set()
        search_calls = 0
        browse_calls = 0
        for step in trajectory.get("result", []):
            if not isinstance(step, dict) or step.get("type") != "tool_call":
                continue
            tool = str(step.get("tool_name", ""))
            arguments = step.get("arguments")
            output = step.get("output", "")
            if tool == "search":
                search_calls += 1
                exposed.update(parse_ids(output))
            elif tool in {"visit", "get_document"}:
                browse_calls += 1
                browsed.update(parse_ids(arguments))
                browsed.update(parse_ids(output))
        unselected = exposed - browsed
        rows.append({
            "file": path.name,
            "exposed_documents": len(exposed),
            "browsed_documents": len(browsed),
            "exposed_unbrowsed_documents": len(unselected),
            "search_calls": search_calls,
            "browse_calls": browse_calls,
            "has_exposed_negative_candidates": bool(unselected),
        })
    total_exposed = sum(row["exposed_documents"] for row in rows)
    total_browsed = sum(row["browsed_documents"] for row in rows)
    total_unselected = sum(row["exposed_unbrowsed_documents"] for row in rows)
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"file_count": len(paths), "files_sha256": hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest(), "raw_content_committed": False},
        "aggregate": {
            "trajectories": len(rows),
            "search_calls": sum(row["search_calls"] for row in rows),
            "browse_calls": sum(row["browse_calls"] for row in rows),
            "exposed_documents": total_exposed,
            "browsed_documents": total_browsed,
            "exposed_unbrowsed_documents": total_unselected,
            "trajectories_with_exposed_unbrowsed_candidates": sum(row["has_exposed_negative_candidates"] for row in rows),
            "exposed_unbrowsed_fraction": round(total_unselected / total_exposed, 6) if total_exposed else 0.0,
        },
        "rows": rows,
        "claim_boundary": {"exposure_negative_availability_measured": True, "negative_labels_established": False, "correctness_established": False, "reason": "An exposed-but-unbrowsed document is a candidate negative under LRAT's construction, not an independently irrelevant or incorrect item."},
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(list(args.root.glob("**/*.json")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
