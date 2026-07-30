#!/usr/bin/env python3
"""Prepare the pinned Fable-5 top-level Claude cohort without durable paths.

The Hugging Face archive contains both top-level Claude Code histories and
session-scoped subagent histories.  This preparer admits only files exactly two
path components below ``claude/projects`` (project directory plus JSONL file),
verifies every JSONL object, and materializes a content-addressed quarantine.
The committed manifest therefore needs no native session ID or workstation
path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


DATASET_ID = "Glint-Research/Fable-5-traces"
DATASET_REVISION = "e05c417852fc59fd8da758e68b352732423ca0cb"
DATASET_LICENSE = "AGPL-3.0"
ADAPTER = "claude_native_context_transition_v1"
SELECTOR = "exactly_two_components_below_claude_projects"


class PreparationError(ValueError):
    """Raised when the downloaded source does not match the frozen cohort."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_jsonl(raw: bytes) -> int:
    records = 0
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PreparationError(
                f"invalid JSONL object at content-local line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise PreparationError(
                f"JSONL object required at content-local line {line_number}"
            )
        records += 1
    if records == 0:
        raise PreparationError("empty JSONL file is not admissible")
    return records


def discover(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    """Return path-minimized receipts and bytes for the top-level cohort."""

    root = source_root.resolve(strict=True)
    receipts: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    native_paths_seen = 0
    excluded_nested = 0
    for path in sorted(root.rglob("*.jsonl")):
        native_paths_seen += 1
        relative = path.relative_to(root)
        if len(relative.parts) != 2:
            excluded_nested += 1
            continue
        if path.is_symlink():
            raise PreparationError("symlinked source files are forbidden")
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        if digest in payloads:
            raise PreparationError("duplicate top-level content digest")
        records = _validate_jsonl(raw)
        payloads[digest] = raw
        receipts.append(
            {
                "path": f"sha256/{digest}.jsonl",
                "bytes": len(raw),
                "sha256": digest,
                "records": records,
            }
        )
    receipts.sort(key=lambda item: str(item["sha256"]))
    if not receipts:
        raise PreparationError("no top-level Claude histories discovered")
    audit = {
        "native_jsonl_files_seen": native_paths_seen,
        "top_level_files_admitted": len(receipts),
        "nested_or_subagent_files_excluded": excluded_nested,
    }
    return receipts, payloads | {"__audit__": stable_json(audit).encode("utf-8")}


def build_manifest(source_root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    receipts, payloads = discover(source_root)
    audit = json.loads(payloads.pop("__audit__").decode("utf-8"))
    manifest = {
        "schema_version": "trace-dataset-manifest-v1",
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "license": DATASET_LICENSE,
        "harness": "claude_code",
        "adapter": ADAPTER,
        "source_selection": {
            "source_subtree": "claude/projects",
            "selector": SELECTOR,
            "top_level_human_facing_assumption": (
                "top_level_is_not_proof_of_human_authorship"
            ),
            "native_object_paths_committed": False,
            "native_session_ids_committed": False,
            **audit,
        },
        "download_policy": {
            "raw_data_committed": False,
            "temporary_cache_only": True,
            "content_addressed_quarantine_required": True,
            "content_free_aggregate_only": True,
        },
        "cohort": {
            "source_files": receipts,
            "import_authority": {
                "tenant_id": "public-research",
                "owner_subject_id": "fable5-source-stratum",
                "team_id": "trace-intelligence-study",
                "classification": 1,
                "purpose": "trace-memory-research",
                "authorization_epoch": 1,
            },
        },
    }
    manifest["cohort_receipt_sha256"] = sha256_bytes(
        stable_json(receipts).encode("utf-8")
    )
    return manifest, payloads


def _structural_binding(manifest: Mapping[str, Any]) -> dict[str, Any]:
    cohort = manifest.get("cohort")
    if not isinstance(cohort, dict):
        raise PreparationError("manifest cohort is required")
    return {
        "schema_version": manifest.get("schema_version"),
        "dataset_id": manifest.get("dataset_id"),
        "dataset_revision": manifest.get("dataset_revision"),
        "license": manifest.get("license"),
        "harness": manifest.get("harness"),
        "adapter": manifest.get("adapter"),
        "source_selection": manifest.get("source_selection"),
        "download_policy": manifest.get("download_policy"),
        "cohort": {
            "source_files": cohort.get("source_files"),
            "import_authority": cohort.get("import_authority"),
        },
        "cohort_receipt_sha256": manifest.get("cohort_receipt_sha256"),
    }


def verify_manifest(
    generated: Mapping[str, Any],
    frozen_path: Path,
) -> dict[str, Any]:
    try:
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreparationError("cannot load frozen manifest") from exc
    if not isinstance(frozen, dict):
        raise PreparationError("frozen manifest must be an object")
    if _structural_binding(generated) != _structural_binding(frozen):
        raise PreparationError("downloaded cohort does not match frozen manifest")
    return frozen


def materialize(
    receipts: list[Mapping[str, Any]],
    payloads: Mapping[str, bytes],
    output_root: Path,
) -> None:
    root = output_root.resolve()
    target_dir = root / "sha256"
    target_dir.mkdir(parents=True, exist_ok=True)
    for receipt in receipts:
        digest = str(receipt["sha256"])
        raw = payloads.get(digest)
        if raw is None:
            raise PreparationError("frozen receipt has no downloaded payload")
        target = target_dir / f"{digest}.jsonl"
        temporary = target.with_suffix(".jsonl.tmp")
        temporary.write_bytes(raw)
        os.replace(temporary, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--freeze",
        action="store_true",
        help="write a new frozen manifest; otherwise verify the existing one",
    )
    args = parser.parse_args()

    generated, payloads = build_manifest(args.source_root)
    if args.freeze:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(generated, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        frozen = generated
    else:
        frozen = verify_manifest(generated, args.manifest)
    cohort = frozen["cohort"]
    materialize(cohort["source_files"], payloads, args.output_root)
    print(
        stable_json(
            {
                "status": "ok",
                "dataset_id": DATASET_ID,
                "revision": DATASET_REVISION,
                "source_files_verified": len(cohort["source_files"]),
                "source_bytes_verified": sum(
                    int(item["bytes"]) for item in cohort["source_files"]
                ),
                "native_paths_emitted": False,
                "native_identifiers_emitted": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
