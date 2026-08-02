#!/usr/bin/env python3
"""Verify the aggregate-only WMH-BIRD schema exposure audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-wmh-bird-schema-exposure-audit-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected WMH-BIRD exposure schema")
    aggregate = result.get("aggregate", {})
    keys = ("traces", "schema_table_exposures", "consumed_table_identifiers", "exposed_unconsumed_table_identifiers", "traces_with_exposed_unconsumed_tables")
    if any(not isinstance(aggregate.get(key), int) or aggregate[key] < 0 for key in keys):
        raise ValueError("invalid aggregate counts")
    if aggregate["consumed_table_identifiers"] + aggregate["exposed_unconsumed_table_identifiers"] != aggregate["schema_table_exposures"]:
        raise ValueError("table counts do not reconcile")
    fraction = aggregate.get("exposed_unconsumed_fraction")
    if not isinstance(fraction, (float, int)) or not 0.0 <= float(fraction) <= 1.0:
        raise ValueError("invalid unconsumed fraction")
    if len(result.get("rows", [])) != aggregate["traces"]:
        raise ValueError("row count mismatch")
    claim = result.get("claim_boundary", {})
    if claim.get("semantic_negative_labels_established") is not False or claim.get("validated_artifact_utility_measured") is not False:
        raise ValueError("claim boundary overstates evidence")
    return {"schema_version": "frankengate-wmh-bird-schema-exposure-verification-v1", "source_result_sha256": file_hash(result_path), "traces_verified": aggregate["traces"], "reconciliation_verified": True, "claim_boundary_verified": True, "verification_passed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
