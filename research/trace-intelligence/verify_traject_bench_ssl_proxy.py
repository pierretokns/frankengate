#!/usr/bin/env python3
"""Verify the content-minimized SSL-shaped TRAJECT-Bench receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-ssl-proxy-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected SSL-proxy schema")
    if int(result.get("records_evaluated", 0)) <= 0:
        raise ValueError("no records evaluated")
    if result.get("source", {}).get("raw_content_committed") is not False:
        raise ValueError("raw content disclosure boundary changed")
    protocol = result.get("protocol", {})
    if protocol.get("ssl_reproduction") is not False or protocol.get("weights_frozen_before_execution") is not True:
        raise ValueError("proxy or freeze boundary changed")
    claim = result.get("claim_boundary", {})
    for field in ("grounded_scene_graph_measured", "logical_effect_labels_measured", "enterprise_alias_quality_measured", "skill_or_artifact_utility_measured"):
        if claim.get(field) is not False:
            raise ValueError(f"claim boundary overstates {field}")
    required_arms = {"name", "ssl_scheduling", "ssl_structural", "ssl_logical", "ssl_rich"}
    seen_arms: set[str] = set()
    for key, aggregate in result.get("aggregates", {}).items():
        parts = key.split("/")
        if len(parts) != 3:
            raise ValueError(f"malformed aggregate key: {key}")
        seen_arms.add(parts[-1])
        if int(aggregate.get("records", 0)) <= 0:
            raise ValueError(f"empty aggregate: {key}")
        for metric in ("mrr", "recall_at_1", "recall_at_5", "recall_at_10", "exact_target_set_at_target_count"):
            value = aggregate.get(metric)
            if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"invalid metric {key}.{metric}")
    if seen_arms != required_arms:
        raise ValueError(f"missing arms: {required_arms - seen_arms}")
    return {
        "schema_version": "traject-bench-ssl-proxy-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "records_verified": int(result["records_evaluated"]),
        "arms_verified": sorted(seen_arms),
        "claim_boundary_verified": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = verify(args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
