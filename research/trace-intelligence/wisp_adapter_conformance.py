#!/usr/bin/env python3
"""Run aggregate, content-free conformance over a Wisp corpus snapshot."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

from wisp_claude_code_adapter import (
    assert_no_silent_drops,
    canonicalize_wisp_file,
)


def run_conformance(
    corpus_root: Path, manifest: dict[str, Any] | Path
) -> dict[str, Any]:
    totals: collections.Counter[str] = collections.Counter()
    loss_categories: collections.Counter[str] = collections.Counter()
    unknown_categories: collections.Counter[str] = collections.Counter()
    correlation_statuses: collections.Counter[str] = collections.Counter()
    trace_ids: set[str] = set()

    files = sorted(corpus_root.rglob("*.jsonl"))
    for path in files:
        trajectory = canonicalize_wisp_file(path, corpus_root, manifest)
        assert_no_silent_drops(trajectory)
        receipt = trajectory["loss_receipt"]
        totals.update(
            {
                "files": 1,
                "source_records": receipt["source_record_count"],
                "source_native_list_blocks": receipt[
                    "source_content_block_count"
                ],
                "canonical_events": receipt["canonical_event_count"],
                "silently_dropped_records": receipt[
                    "silently_dropped_record_count"
                ],
                "silently_dropped_blocks": receipt[
                    "silently_dropped_content_block_count"
                ],
            }
        )
        loss_categories.update(item["category"] for item in receipt["losses"])
        unknown_categories.update(
            item["category"] for item in receipt["unknowns"]
        )
        for event in trajectory["events"]:
            if event["kind"] in ("tool.completed", "tool.failed"):
                correlation_statuses[event.get("correlation_status", "missing")] += 1
        trace_ids.add(trajectory["trace_id"])

    manifest_value = (
        json.loads(manifest.read_text(encoding="utf-8"))
        if isinstance(manifest, Path)
        else manifest
    )
    return {
        "schema_version": "wisp-adapter-conformance-result-v1",
        "source": {
            "dataset_id": manifest_value["dataset_id"],
            "dataset_revision": manifest_value["dataset_revision"],
            "license": manifest_value["license"],
        },
        "counts": {
            **dict(totals),
            "unique_trace_ids": len(trace_ids),
        },
        "loss_categories": dict(sorted(loss_categories.items())),
        "unknown_categories": dict(sorted(unknown_categories.items())),
        "tool_result_correlation": dict(sorted(correlation_statuses.items())),
        "privacy_contract": {
            "raw_transcripts_committed": False,
            "content_serialized": False,
            "paths_or_native_ids_serialized": False,
            "aggregate_counts_only": True,
        },
        "claim_limits": [
            "format conformance does not establish task correctness",
            "tool-result correlation does not establish causal recovery",
            "one public contributor does not establish enterprise generality",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_root", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run_conformance(args.corpus_root.resolve(), args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
