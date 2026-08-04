#!/usr/bin/env python3
"""Mine a deterministic, content-free BIRD SQL procedure from evidence traces.

This is a deliberately transparent baseline for the independent factorial. It
does not ask a model to summarize traces and never writes prompts, SQL, rows,
or trace identifiers. The emitted procedure is frozen before held-out model
calls and is not itself evidence of utility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-sql-trace-miner-v1"
PROCEDURE = """Before answering a database question:
1. Inspect the available schema and use the exact table and column names.
2. Map the requested entities and relationships through declared foreign keys.
3. Translate every filter and comparison from the question into an explicit SQL predicate.
4. Use joins or EXISTS only where the relationship requires them; preserve the requested output columns and order.
5. Produce one read-only SELECT or WITH query and stop after the query is complete.
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attribute_map(span: dict[str, Any]) -> dict[str, Any]:
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


def mine(*, traces: Path, tasks: Path, evidence_families: set[str]) -> dict[str, Any]:
    task_family: dict[str, str] = {}
    for line in tasks.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if isinstance(row, dict) and isinstance(row.get("task_id"), str):
            data = row.get("data")
            if isinstance(data, dict) and isinstance(data.get("db_name"), str):
                task_family[row["task_id"]] = data["db_name"]

    traces_by_id: dict[str, list[str]] = {}
    metadata_by_id: dict[str, dict[str, Any]] = {}
    for line in traces.read_text(encoding="utf-8").splitlines():
        span = json.loads(line)
        if not isinstance(span, dict) or not isinstance(span.get("traceId"), str):
            continue
        trace_id = span["traceId"]
        attrs = attribute_map(span)
        traces_by_id.setdefault(trace_id, []).append(str(attrs.get("gen_ai.operation.name", "missing")))
        raw_metadata = attrs.get("wmh.trace.metadata")
        if isinstance(raw_metadata, str):
            metadata = json.loads(raw_metadata)
            if isinstance(metadata, dict):
                metadata_by_id[trace_id] = metadata

    cycles: Counter[str] = Counter()
    rewards: Counter[str] = Counter()
    admitted = 0
    for trace_id, metadata in metadata_by_id.items():
        family = task_family.get(str(metadata.get("base_task_id")))
        if family not in evidence_families:
            continue
        admitted += 1
        cycles["tool_cycles"] += sum(op == "execute_tool" for op in traces_by_id.get(trace_id, []))
        if metadata.get("reward") == 1.0:
            rewards["solved"] += 1
        elif metadata.get("reward") == 0.0:
            rewards["unsolved"] += 1
        else:
            rewards["other"] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "trace_sha256": sha256_file(traces),
            "task_sha256": sha256_file(tasks),
            "evidence_families": sorted(evidence_families),
        },
        "evidence": {
            "admitted_traces": admitted,
            "tool_cycles": cycles["tool_cycles"],
            "rewards": dict(sorted(rewards.items())),
            "operation_sequence_observed": "chat -> execute_tool repeated",
        },
        "procedure": PROCEDURE,
        "procedure_sha256": hashlib.sha256(PROCEDURE.encode("utf-8")).hexdigest(),
        "claim_boundary": {
            "candidate_frozen_before_heldout": True,
            "causal_skill_benefit_confirmed": False,
            "model_synthesis_used": False,
            "reason": "Transparent structural baseline; utility requires the separate family-disjoint factorial.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--evidence-family", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--procedure-output", type=Path, required=True)
    args = parser.parse_args()
    result = mine(
        traces=args.traces,
        tasks=args.tasks,
        evidence_families=set(args.evidence_family),
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.procedure_output.write_text(result["procedure"], encoding="utf-8")
    print(json.dumps(result["evidence"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
