#!/usr/bin/env python3
"""Audit schema-exposed but unconsumed SQL identifiers in WMH-BIRD traces.

This is an LRAT-inspired exposure audit for SQL agents. Schema tables shown by
the environment are candidates; tables referenced by the recorded candidate
SQL are consumed identifiers. Unconsumed tables are candidate negatives only,
not reviewed semantic negatives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-wmh-bird-schema-exposure-audit-v1"
CREATE_TABLE = re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)", re.I)
SQL_REFERENCE = re.compile(r"\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)|\b([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*[A-Za-z_][A-Za-z0-9_]*", re.I)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def attributes(span: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in span.get("attributes", []):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        value = item.get("value")
        if isinstance(value, dict):
            for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
                if key in value:
                    values[item["key"]] = value[key]
                    break
    return values


def audit(path: Path) -> dict[str, Any]:
    traces: dict[str, dict[str, Any]] = {}
    malformed = 0
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            span = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(span, dict) or not isinstance(span.get("traceId"), str):
            malformed += 1
            continue
        attrs = attributes(span)
        record = traces.setdefault(span["traceId"], {"tables": set(), "sql": "", "metadata": None, "tool_cycles": 0})
        tool_message = attrs.get("gen_ai.tool.message")
        if isinstance(tool_message, str):
            record["tables"].update(CREATE_TABLE.findall(tool_message))
        if attrs.get("gen_ai.operation.name") == "execute_tool":
            record["tool_cycles"] += 1
        raw_metadata = attrs.get("wmh.trace.metadata")
        if isinstance(raw_metadata, str):
            try:
                metadata = json.loads(raw_metadata)
            except json.JSONDecodeError:
                metadata = None
            if isinstance(metadata, dict):
                record["metadata"] = metadata
                if isinstance(metadata.get("final_answer"), str):
                    record["sql"] = metadata["final_answer"]
    rows: list[dict[str, Any]] = []
    reward_counts: Counter[str] = Counter()
    for trace_id, record in traces.items():
        tables = {str(value).casefold() for value in record["tables"]}
        used: set[str] = set()
        for match in SQL_REFERENCE.finditer(record["sql"]):
            used.update(str(value).casefold() for value in match.groups() if value)
        used &= tables
        unconsumed = tables - used
        metadata = record.get("metadata") or {}
        reward = metadata.get("reward")
        reward_key = str(reward)
        reward_counts[reward_key] += 1
        rows.append({
            "trace_hash": hashlib.sha256(trace_id.encode()).hexdigest(),
            "schema_tables": len(tables),
            "consumed_tables": len(used),
            "exposed_unconsumed_tables": len(unconsumed),
            "has_exposed_unconsumed_tables": bool(unconsumed),
            "reward": reward,
            "tool_cycles": int(record["tool_cycles"]),
        })
    exposed = sum(row["schema_tables"] for row in rows)
    consumed = sum(row["consumed_tables"] for row in rows)
    unconsumed = sum(row["exposed_unconsumed_tables"] for row in rows)
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"trace_sha256": file_hash(path), "raw_content_committed": False, "malformed_rows": malformed},
        "aggregate": {
            "traces": len(rows),
            "schema_table_exposures": exposed,
            "consumed_table_identifiers": consumed,
            "exposed_unconsumed_table_identifiers": unconsumed,
            "exposed_unconsumed_fraction": round(unconsumed / exposed, 6) if exposed else 0.0,
            "traces_with_exposed_unconsumed_tables": sum(row["has_exposed_unconsumed_tables"] for row in rows),
            "reward_counts": dict(sorted(reward_counts.items())),
        },
        "rows": rows,
        "claim_boundary": {"schema_exposure_measured": True, "candidate_negative_availability_measured": True, "semantic_negative_labels_established": False, "validated_artifact_utility_measured": False, "reason": "Schema tables are environment-exposed candidates; unused tables may be skipped for authority, cost, redundancy, or task reasons."},
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.traces)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
