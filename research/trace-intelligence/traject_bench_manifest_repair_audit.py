#!/usr/bin/env python3
"""Audit reference-tool names missing from TRAJECT-Bench candidate manifests.

Only deterministic exact and uniquely normalized matches are considered. Fuzzy
matches are reported as unresolved rather than silently changing benchmark
labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-manifest-repair-audit-v1"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def tool_names(row: dict[str, Any]) -> set[str]:
    value = row.get("tool list", row.get("tool_list", []))
    return {str(item.get("tool name")) for item in value if isinstance(item, dict) and item.get("tool name")}


def audit(root: Path) -> dict[str, Any]:
    tool_files = {path.stem.removesuffix("_tool"): path for path in sorted((root / "tools").glob("*_tool.json"))}
    all_path = root / "tools" / "all_tools.json"
    all_tools = json.loads(all_path.read_text(encoding="utf-8"))
    all_names = {str(item.get("tool name")) for item in all_tools if isinstance(item, dict) and item.get("tool name")}
    normalized_candidates: dict[str, list[str]] = defaultdict(list)
    for name in all_names:
        normalized_candidates[normalize_name(name)].append(name)

    files = sorted(root.glob("parallel/*/*.json")) + sorted(root.glob("sequential/*/*.json"))
    rows = exact_rows = normalized_complete_rows = partial_rows = unresolved_rows = 0
    missing_occurrences = mapped_occurrences = unresolved_occurrences = 0
    unique_missing_names: Counter[str] = Counter()
    mapping_pairs: Counter[tuple[str, str]] = Counter()

    for path in files:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            continue
        for row in value:
            if not isinstance(row, dict):
                continue
            rows += 1
            targets = tool_names(row)
            if targets <= all_names:
                exact_rows += 1
                continue
            mapped: list[tuple[str, str]] = []
            unresolved: list[str] = []
            for target in sorted(targets - all_names):
                unique_missing_names[target] += 1
                matches = normalized_candidates.get(normalize_name(target), [])
                if len(matches) == 1:
                    mapped.append((target, matches[0]))
                    mapping_pairs[(target, matches[0])] += 1
                else:
                    unresolved.append(target)
            missing_occurrences += len(mapped) + len(unresolved)
            mapped_occurrences += len(mapped)
            unresolved_occurrences += len(unresolved)
            if unresolved:
                unresolved_rows += 1
                if mapped:
                    partial_rows += 1
            else:
                normalized_complete_rows += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"root_name": root.name, "file_count": len(files), "data_files_sha256": stable_hash(sorted(file_sha256(path) for path in files)), "raw_content_committed": False},
        "rows": rows,
        "exact_candidate_manifest_rows": exact_rows,
        "uniquely_normalized_repair_rows": normalized_complete_rows,
        "partially_repairable_rows": partial_rows,
        "unresolved_rows": unresolved_rows,
        "missing_name_occurrences": missing_occurrences,
        "unique_normalized_name_occurrences_repaired": mapped_occurrences,
        "unresolved_name_occurrences": unresolved_occurrences,
        "unique_missing_name_count": len(unique_missing_names),
        "missing_name_frequency_histogram": dict(sorted(Counter(unique_missing_names.values()).items())),
        "unique_repair_pair_count": len(mapping_pairs),
        "claim_boundary": {"automatic_fuzzy_repair_authorized": False, "benchmark_labels_changed": False, "reason": "Only unique normalized matches are identified; unresolved or ambiguous names remain excluded until the source manifest is repaired or adjudicated."},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("rows", "exact_candidate_manifest_rows", "uniquely_normalized_repair_rows", "unresolved_rows", "unique_missing_name_count")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
