#!/usr/bin/env python3
"""Verify the content-free cross-corpus SQL signature receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-cross-corpus-sql-artifact-signatures-verification-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    unsigned = dict(result)
    expected = unsigned.pop("result_sha256", None)
    overlap = result.get("cross_corpus_overlap", {})
    checks = {
        "schema": result.get("schema_version") == "frankengate-cross-corpus-sql-artifact-signatures-v1",
        "result_hash": expected == digest(unsigned),
        "corpus_count": set(result.get("sources", {})) == {"bird", "defog"},
        "counts_present": all(
            set(result.get("template_counts", {}).get(name, {})) == {"unique_exact_templates", "unique_structural_templates", "unique_coarse_operator_shapes"}
            for name in ("bird", "defog")
        ),
        "collision_rate_bounded": all(
            overlap.get(key) is None or 0 <= overlap[key] <= 1
            for key in ("structural_collision_rate", "coarse_collision_rate")
        ),
        "raw_content_absent": result.get("raw_content_committed") is False,
        "claim_boundary": result.get("claim_boundary", {}).get("cross_corpus_executable_reuse_established") is False,
    }
    verification = {
        "schema_version": SCHEMA_VERSION,
        "passed": all(checks.values()),
        "checks": checks,
        "result_sha256": expected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, sort_keys=True))
    return 0 if verification["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
