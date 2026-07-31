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

from canonical_projection_e0 import (
    canonical_to_atif_e0,
    canonical_to_openinference_otel,
)


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
    atif_projected_rows = 0
    otel_projected_rows = 0
    atif_loss_items = 0
    otel_loss_items = 0
    harnesses: set[str] = set()
    benchmarks: set[str] = set()
    for row in rows:
        harnesses.add(str(row.get("harness") or ""))
        benchmarks.add(str(row.get("benchmark") or ""))
        canonical_events = []
        for index, span in enumerate(row.get("spans") or []):
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
            canonical_events.append(
                {
                    "event_id": f"e{index:06d}",
                    "sequence": index,
                    "kind": (
                        "tool_call"
                        if "tool" in str(span.get("name", "")).lower()
                        else "llm_call"
                    ),
                    "observation_status": "observed",
                    "source_role": "agent",
                    "content": None,
                    "span_id": span.get("span_id"),
                    "start_time": span.get("start_time"),
                    "end_time": span.get("end_time"),
                    "status_code": (span.get("status") or {}).get("code"),
                }
            )
        canonical = {
            "schema_version": "canonical-trajectory-v1",
            "trace_id": str(row.get("session_id") or "row"),
            "source": {
                "dataset_id": "DiscoPosse/agent-llm-traces",
                "dataset_revision": dataset_revision,
                "adapter": "bounded-otel-shard-v1",
            },
            "task": {"task_id": str(row.get("session_id") or "row")},
            "events": canonical_events,
            "outcome": {"value": "observed", "source": "dataset"},
        }
        atif, atif_receipt = canonical_to_atif_e0(canonical)
        otel, otel_receipt = canonical_to_openinference_otel(canonical)
        del atif, otel
        atif_projected_rows += 1
        otel_projected_rows += 1
        atif_loss_items += sum(atif_receipt.get("item_category_counts", {}).values())
        otel_loss_items += sum(otel_receipt.get("item_category_counts", {}).values())
    return {
        "schema_version": "fg-hf-otel-shard-audit-v1",
        "dataset_id": "DiscoPosse/agent-llm-traces",
        "dataset_revision": dataset_revision,
        "source_sha256": _sha256(path),
        "source_file_bytes": path.stat().st_size,
        "rows": len(rows),
        "spans": span_count,
        "tool_related_spans": tool_span_count,
        "atif_projected_rows": atif_projected_rows,
        "openinference_otel_projected_rows": otel_projected_rows,
        "atif_projection_loss_items": atif_loss_items,
        "openinference_otel_projection_loss_items": otel_loss_items,
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
