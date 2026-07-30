#!/usr/bin/env python3
"""Offline integrity checks for the committed research artifact.

This verifier intentionally does not download datasets, call models, connect to
PostgreSQL, or inspect a user's harness home. It checks that committed manifests,
schemas, fixtures, and aggregate results are parseable, source-pinned, content
minimized, and explicit about raw-data handling.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parent
MANIFEST_DIR = ROOT / "configs" / "datasets"
RESULT_DIR = ROOT / "experiments" / "results"
SCHEMA_DIR = ROOT / "schemas"
FIXTURE_DIR = ROOT / "fixtures" / "governed-v1"

REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
FORBIDDEN_RESULT_PATTERNS = {
    "home_path": re.compile(r"(?:/Users/|/home/|~/(?:\\.claude|\\.codex))"),
    "credential_label": re.compile(
        r"(?i)(?:api[_ -]?key|access[_ -]?token|authorization|password)"
        r"\s*[:=]\s*[\"']?[^\"'\\s]{8,}"
    ),
}
RAW_SUFFIXES = {".parquet", ".arrow", ".jsonl", ".sqlite", ".db"}


class ReproducibilityError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproducibilityError(f"{path}: invalid JSON: {exc}") from exc


def validate_manifests() -> int:
    paths = sorted(MANIFEST_DIR.glob("*.json"))
    if not paths:
        raise ReproducibilityError("no dataset manifests found")
    for path in paths:
        value = load_json(path)
        if value.get("schema_version") != "trace-dataset-manifest-v1":
            raise ReproducibilityError(f"{path}: unsupported manifest version")
        revision = value.get("dataset_revision")
        if not isinstance(revision, str) or not REVISION_RE.fullmatch(revision):
            raise ReproducibilityError(
                f"{path}: dataset_revision must be a 40-character commit"
            )
        if not value.get("dataset_id") or not value.get("source_url"):
            raise ReproducibilityError(f"{path}: source identity is incomplete")
        if not value.get("license"):
            raise ReproducibilityError(f"{path}: license must be explicit")
        policy = value.get("download_policy")
        pilot = value.get("pilot_sample")
        privacy = value.get("privacy_review")
        raw_committed = next(
            (
                section["raw_data_committed"]
                for section in (policy, pilot, privacy)
                if isinstance(section, dict)
                and "raw_data_committed" in section
            ),
            None,
        )
        if raw_committed is not False:
            raise ReproducibilityError(
                f"{path}: raw_data_committed must be explicitly false"
            )
    return len(paths)


def validate_results() -> int:
    paths = sorted(RESULT_DIR.glob("*.json"))
    if not paths:
        raise ReproducibilityError("no aggregate result artifacts found")
    for path in paths:
        value = load_json(path)
        if not isinstance(value, dict) or not value.get("schema_version"):
            raise ReproducibilityError(f"{path}: schema_version is required")
        serialized = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN_RESULT_PATTERNS.items():
            if pattern.search(serialized):
                raise ReproducibilityError(
                    f"{path}: aggregate result violates {label} minimization"
                )
    return len(paths)


def validate_governed_fixtures() -> int:
    schema = load_json(SCHEMA_DIR / "canonical-trajectory.schema.json")
    paths = sorted(FIXTURE_DIR.glob("*.json"))
    if not paths:
        raise ReproducibilityError("no governed conformance fixtures found")
    validator = jsonschema.Draft202012Validator(schema)
    for path in paths:
        errors = sorted(
            validator.iter_errors(load_json(path)),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            rendered = "; ".join(error.message for error in errors[:3])
            raise ReproducibilityError(f"{path}: schema errors: {rendered}")
    return len(paths)


def validate_no_raw_corpus_files() -> None:
    candidates = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in RAW_SUFFIXES
        and "fixtures" not in path.parts
        and ".venv" not in path.parts
    ]
    if candidates:
        names = ", ".join(str(path.relative_to(ROOT)) for path in candidates)
        raise ReproducibilityError(f"raw-like corpus files are committed: {names}")


def main() -> int:
    manifest_count = validate_manifests()
    result_count = validate_results()
    fixture_count = validate_governed_fixtures()
    validate_no_raw_corpus_files()
    print(
        json.dumps(
            {
                "status": "ok",
                "dataset_manifests": manifest_count,
                "aggregate_results": result_count,
                "governed_fixtures": fixture_count,
                "raw_corpus_files_committed": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
