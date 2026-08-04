#!/usr/bin/env python3
"""Verify the aggregate-only LRAT exposure audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-lrat-exposure-negative-audit-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected LRAT exposure schema")
    aggregate = result.get("aggregate", {})
    for key in ("trajectories", "search_calls", "browse_calls", "exposed_documents", "browsed_documents", "exposed_unbrowsed_documents"):
        if not isinstance(aggregate.get(key), int) or aggregate[key] < 0:
            raise ValueError(f"invalid aggregate: {key}")
    if aggregate["exposed_unbrowsed_documents"] > aggregate["exposed_documents"]:
        raise ValueError("unbrowsed count exceeds exposed count")
    fraction = aggregate.get("exposed_unbrowsed_fraction")
    if not isinstance(fraction, (int, float)) or not 0.0 <= float(fraction) <= 1.0:
        raise ValueError("invalid unbrowsed fraction")
    claim = result.get("claim_boundary", {})
    if claim.get("negative_labels_established") is not False or claim.get("correctness_established") is not False:
        raise ValueError("claim boundary overstates supervision")
    if len(result.get("rows", [])) != aggregate["trajectories"]:
        raise ValueError("row count mismatch")
    return {"schema_version": "frankengate-lrat-exposure-negative-verification-v1", "source_result_sha256": file_hash(result_path), "trajectories_verified": aggregate["trajectories"], "claim_boundary_verified": True, "verification_passed": True}


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
