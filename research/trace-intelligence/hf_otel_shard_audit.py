#!/usr/bin/env python3
"""Aggregate-only audit of a pinned Hugging Face OTel Parquet shard.

The input is external cache material. No prompts, tool arguments, outputs, or
identifiers are written to the result; only schema/coverage counts and hashes
are emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit(path: Path, *, dataset_revision: str) -> dict[str, Any]:
    table = pq.read_table(path)
    rows = table.to_pylist()
    span_count = 0
    tool_span_count = 0
    error_span_count = 0
    complete_time_count = 0
    input_message_count = 0
    output_message_count = 0
    tool_definition_count = 0
    harnesses: set[str] = set()
    benchmarks: set[str] = set()
    for row in rows:
        harnesses.add(str(row.get("harness") or ""))
        benchmarks.add(str(row.get("benchmark") or ""))
        for span in row.get("spans") or []:
            span_count += 1
            if span.get("start_time") and span.get("end_time"):
                complete_time_count += 1
            # OpenTelemetry status codes are UNSET=0, OK=1, ERROR=2.
            if span.get("status", {}).get("code") == 2:
                error_span_count += 1
            attrs = span.get("attributes") or {}
            input_message_count += bool(attrs.get("gen_ai.input.messages"))
            output_message_count += bool(attrs.get("gen_ai.output.messages"))
            tool_definition_count += bool(attrs.get("gen_ai.tool.definitions"))
            if "tool" in str(span.get("name", "")).lower() or attrs.get(
                "gen_ai.tool.definitions"
            ):
                tool_span_count += 1
    return {
        "schema_version": "fg-hf-otel-shard-audit-v1",
        "dataset_id": "DiscoPosse/agent-llm-traces",
        "dataset_revision": dataset_revision,
        "source_sha256": _sha256(path),
        "source_file_bytes": path.stat().st_size,
        "rows": len(rows),
        "spans": span_count,
        "tool_related_spans": tool_span_count,
        "error_spans": error_span_count,
        "complete_timestamp_spans": complete_time_count,
        "rows_with_input_messages": input_message_count,
        "rows_with_output_messages": output_message_count,
        "rows_with_tool_definitions": tool_definition_count,
        "harnesses": sorted(harnesses - {""}),
        "benchmarks": sorted(benchmarks - {""}),
        "raw_content_emitted": False,
        "enterprise_behavior_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.input, dataset_revision=args.dataset_revision)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
