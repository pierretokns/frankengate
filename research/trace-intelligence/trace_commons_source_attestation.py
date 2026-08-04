#!/usr/bin/env python3
"""Attest a temporary Trace Commons checkout against its pinned manifest.

The output is aggregate-only: it contains no transcript fields, rows, paths,
identifiers, or timestamps.  The manifest itself supplies the expected source
identity; this tool verifies file inventory, byte counts, line counts, and
SHA-256 values before any analysis result is admitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate.trace-commons-source-attestation.v1"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attest(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    expected = manifest.get("source_files")
    if not isinstance(expected, list) or not expected:
        raise ValueError("manifest source_files must be a non-empty list")
    expected_paths = {str(item["path"]) for item in expected}
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.jsonl")
        if path.is_file()
    }
    missing = expected_paths - actual_paths
    extra = actual_paths - expected_paths
    mismatched_bytes = 0
    mismatched_records = 0
    mismatched_hashes = 0
    total_bytes = 0
    total_records = 0
    expected_by_path = {str(item["path"]): item for item in expected}
    file_hashes: list[str] = []
    for relative in sorted(expected_paths & actual_paths):
        path = root / relative
        raw = path.read_bytes()
        total_bytes += len(raw)
        records = len(raw.splitlines())
        total_records += records
        item = expected_by_path[relative]
        mismatched_bytes += int(int(item.get("bytes", -1)) != len(raw))
        mismatched_records += int(int(item.get("records", -1)) != records)
        digest = _sha256_file(path)
        file_hashes.append(digest)
        mismatched_hashes += int(item.get("sha256") != digest)
    inventory_digest = _sha256_bytes(
        "\n".join(sorted(file_hashes)).encode("utf-8")
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": manifest.get("dataset_id"),
        "dataset_revision": manifest.get("dataset_revision"),
        "license": manifest.get("license"),
        "expected_file_count": len(expected_paths),
        "actual_file_count": len(actual_paths),
        "missing_file_count": len(missing),
        "extra_file_count": len(extra),
        "mismatched_bytes": mismatched_bytes,
        "mismatched_records": mismatched_records,
        "mismatched_hashes": mismatched_hashes,
        "total_bytes": total_bytes,
        "total_records": total_records,
        "inventory_digest": inventory_digest,
        "manifest_digest": _sha256_bytes(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ),
        "attestation": "passed"
        if not (
            missing
            or extra
            or mismatched_bytes
            or mismatched_records
            or mismatched_hashes
        )
        else "failed",
        "raw_content_emitted": False,
    }
    result["result_sha256"] = _sha256_bytes(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = attest(root, manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["attestation"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
