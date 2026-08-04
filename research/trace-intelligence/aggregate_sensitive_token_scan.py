#!/usr/bin/env python3
"""Fail-closed, aggregate-only sensitive-token scan for JSONL trace cohorts.

The scanner inspects nested string values but never returns, logs, hashes, or
persists a matched candidate value. Results contain fixed-class counts and
hash-verified source receipts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence, Union


SCHEMA_VERSION = "aggregate-sensitive-token-scan-result-v1"
SCANNER_VERSION = "aggregate-sensitive-token-regex-v1"

REDACTION_PATTERN_TEXT = {
    "literal_redacted": (
        r"(?:\[REDACTED\]|<REDACTED>|REDACTED_[A-Z0-9_]+)"
    ),
    "numbered_typed_placeholder": (
        r"<(?:API_KEY|EMAIL|PHONE|IP|PATH|TOKEN|JWT|SECRET|USERNAME|HOST)_\d+>"
    ),
    "scrubbed_typed_placeholder": (
        r"(?:<|\[)(?:PERSON|DEVICE|HOST|PRIVATE_DOMAIN|PROJECT|MEDIA|PATH|LAN_IP)"
        r"(?:_[A-Z0-9]+)*(?:>|\])"
    ),
}

SECRET_PATTERN_TEXT = {
    "openai_or_openrouter_key_candidate": (
        r"\bsk-(?:proj-|or-)?[A-Za-z0-9_-]{20,}\b"
    ),
    "huggingface_token_candidate": r"\bhf_[A-Za-z0-9]{20,}\b",
    "github_token_candidate": r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
    "aws_access_key_candidate": r"\bAKIA[0-9A-Z]{16}\b",
    "jwt_candidate": (
        r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}"
        r"\.[A-Za-z0-9_-]{8,}\b"
    ),
    "private_key_header_candidate": (
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "bearer_token_candidate": r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}",
}

REDACTION_PATTERNS = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in REDACTION_PATTERN_TEXT.items()
}
SECRET_PATTERNS = {
    name: re.compile(
        pattern,
        re.IGNORECASE
        if name == "bearer_token_candidate"
        else 0,
    )
    for name, pattern in SECRET_PATTERN_TEXT.items()
}


class SensitiveScanError(ValueError):
    """Raised before any aggregate result is emitted."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def iter_strings(value: Any) -> Iterator[str]:
    """Yield JSON string leaves without synthesizing scalar text."""

    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


class AggregateSensitiveScanner:
    """Count fixed regex classes without retaining candidate values."""

    def __init__(self) -> None:
        self.strings_scanned = 0
        self.redaction_evidence: Counter[str] = Counter()
        self.secret_candidates: Counter[str] = Counter()

    def scan(self, value: Any) -> None:
        for text in iter_strings(value):
            self.strings_scanned += 1
            for name, pattern in REDACTION_PATTERNS.items():
                # Adding zero deliberately retains the fixed redaction class
                # inventory in the aggregate output.
                self.redaction_evidence[name] += sum(
                    1 for _ in pattern.finditer(text)
                )
            for name, pattern in SECRET_PATTERNS.items():
                for match in pattern.finditer(text):
                    # Redaction markers are evidence of scrubbing, not live
                    # secret candidates. The match is inspected only for this
                    # bounded predicate and is never stored or emitted.
                    if "redact" not in match.group(0).casefold():
                        self.secret_candidates[name] += 1

    def aggregate(self) -> dict[str, Any]:
        redactions = {
            name: int(self.redaction_evidence[name])
            for name in sorted(REDACTION_PATTERNS)
        }
        secret_candidates = {
            name: int(count)
            for name, count in sorted(self.secret_candidates.items())
            if count
        }
        return {
            "strings_scanned": self.strings_scanned,
            "redaction_evidence": redactions,
            "redaction_evidence_total": sum(redactions.values()),
            "possible_secret_regex_candidates": secret_candidates,
            "possible_secret_regex_candidate_total": sum(
                secret_candidates.values()
            ),
            "candidate_interpretation": (
                "regex candidates only; no values emitted and no validity asserted"
            ),
        }


def _load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SensitiveScanError("manifest is unreadable or invalid") from exc
    if not isinstance(value, dict):
        raise SensitiveScanError("manifest must be an object")
    policy = value.get("download_policy")
    if (
        not isinstance(policy, dict)
        or policy.get("raw_data_committed") is not False
    ):
        raise SensitiveScanError(
            "manifest must explicitly prohibit committed raw data"
        )
    return value, sha256_bytes(raw)


def _source_files(manifest: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    cohort = manifest.get("cohort")
    source_files = (
        cohort.get("source_files")
        if isinstance(cohort, dict)
        else manifest.get("source_files")
    )
    if not isinstance(source_files, list) or not source_files:
        raise SensitiveScanError("manifest source file receipts are required")
    if not all(isinstance(item, dict) for item in source_files):
        raise SensitiveScanError("every source receipt must be an object")
    return source_files


def _validated_source(
    root: Path,
    receipt: Mapping[str, Any],
    source_index: int,
) -> tuple[bytes, dict[str, Any]]:
    required = ("path", "bytes", "sha256", "records")
    if any(name not in receipt for name in required):
        raise SensitiveScanError(
            f"source receipt {source_index} is incomplete"
        )
    relative = Path(str(receipt["path"]))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise SensitiveScanError(
            f"source receipt {source_index} escapes the source root"
        )
    unresolved = root / relative
    try:
        resolved = unresolved.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise SensitiveScanError(
            f"source receipt {source_index} cannot be resolved safely"
        ) from exc
    if unresolved.is_symlink():
        raise SensitiveScanError(
            f"source receipt {source_index} is a symbolic link"
        )
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise SensitiveScanError(
            f"source receipt {source_index} is unreadable"
        ) from exc
    if len(raw) != int(receipt["bytes"]):
        raise SensitiveScanError(
            f"source receipt {source_index} byte count mismatch"
        )
    if sha256_bytes(raw) != str(receipt["sha256"]):
        raise SensitiveScanError(
            f"source receipt {source_index} SHA-256 mismatch"
        )
    return raw, {
        "relative_path_sha256": sha256_bytes(
            relative.as_posix().encode("utf-8")
        ),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "declared_records": int(receipt["records"]),
    }


def scan_manifest(
    manifest_path: Union[Path, str],
    source_root: Union[Path, str],
) -> dict[str, Any]:
    """Verify and scan a complete cohort, or raise without a partial result."""

    manifest, manifest_sha256 = _load_manifest(Path(manifest_path))
    source_files = _source_files(manifest)
    root = Path(source_root).resolve()
    scanner = AggregateSensitiveScanner()
    receipts: list[dict[str, Any]] = []
    total_records = 0

    for source_index, receipt in enumerate(source_files):
        raw, verified = _validated_source(
            root,
            receipt,
            source_index,
        )
        source_records = 0
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SensitiveScanError(
                    "source receipt "
                    f"{source_index} has invalid JSON at line {line_number}"
                ) from exc
            if not isinstance(record, dict):
                raise SensitiveScanError(
                    "source receipt "
                    f"{source_index} has a non-object at line {line_number}"
                )
            scanner.scan(record)
            source_records += 1
        if source_records != verified["declared_records"]:
            raise SensitiveScanError(
                f"source receipt {source_index} record count mismatch"
            )
        verified["records"] = source_records
        del verified["declared_records"]
        receipts.append(verified)
        total_records += source_records

    aggregate = scanner.aggregate()
    result = {
        "schema_version": SCHEMA_VERSION,
        "scanner_version": SCANNER_VERSION,
        "scanner_contract": {
            "traversal": "all_nested_dict_and_list_string_leaves",
            "redaction_classes": sorted(REDACTION_PATTERNS),
            "secret_candidate_classes": sorted(SECRET_PATTERNS),
            "redact_literal_secret_candidates_suppressed": True,
            "candidate_values_retained": False,
            "candidate_values_emitted": False,
            "candidate_validity_asserted": False,
            "malformed_or_unverified_source_behavior": "fail_closed_no_result",
        },
        "input_receipts": {
            "manifest_sha256": manifest_sha256,
            "source_file_count": len(receipts),
            "source_bytes": sum(item["bytes"] for item in receipts),
            "source_records": total_records,
            "source_receipt_root_sha256": sha256_bytes(
                stable_json(receipts).encode("utf-8")
            ),
        },
        "aggregate_scan": aggregate,
        "raw_content_emitted": False,
        "source_paths_emitted": False,
        "candidate_values_emitted": False,
    }
    result["result_sha256"] = sha256_bytes(
        stable_json(result).encode("utf-8")
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    args = parse_args()
    try:
        result = scan_manifest(args.manifest, args.source_root)
    except SensitiveScanError as exc:
        print(f"scan failed closed: {exc}", file=sys.stderr)
        return 2
    serialized = json.dumps(result, indent=2, sort_keys=True)
    if args.output is None:
        print(serialized)
    else:
        _write_atomic(args.output, serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
