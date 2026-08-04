#!/usr/bin/env python3
"""Credential-only transform for full-fidelity internal trace research.

This gate intentionally does not redact names, email addresses, phone numbers,
paths, source code, identifiers, or ordinary high-entropy data.
"""

from __future__ import annotations

from collections import Counter
import base64
import copy
import hashlib
import hmac
import json
import os
import pathlib
import re
import tempfile
from typing import Any, Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SCHEMA_VERSION = "frankengate.credential-transform-receipt.v1"
BOUNDARIES = {
    "capture",
    "model_input",
    "model_output",
    "evaluator",
    "index",
    "tool_input",
    "tool_output",
    "replay",
    "egress",
}
EXACT_FIELDS = {
    "authorization": "AUTHORIZATION",
    "proxy-authorization": "AUTHORIZATION",
    "cookie": "SESSION",
    "set-cookie": "SESSION",
    "x-api-key": "API_KEY",
    "api-key": "API_KEY",
    "x-bf-vk": "VIRTUAL_KEY",
    "password": "PASSWORD",
    "passwd": "PASSWORD",
    "passphrase": "PASSWORD",
    "client_secret": "OAUTH_CLIENT_SECRET",
    "access_token": "OAUTH_ACCESS_TOKEN",
    "refresh_token": "OAUTH_REFRESH_TOKEN",
    "id_token": "OAUTH_ID_TOKEN",
    "session_token": "SESSION",
    "oauth_code": "OAUTH_CODE",
    "code_verifier": "OAUTH_PKCE_VERIFIER",
    "api_key": "API_KEY",
    "secret_key": "SECRET_KEY",
    "private_key": "PRIVATE_KEY",
    "webhook_secret": "WEBHOOK_SECRET",
    "aws_access_key_id": "AWS_ACCESS_KEY_ID",
    "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY",
    "aws_session_token": "AWS_SESSION_TOKEN",
    "azure_client_secret": "AZURE_CLIENT_SECRET",
    "sas_token": "AZURE_SAS_TOKEN",
    "gcp_service_account_key": "GCP_SERVICE_ACCOUNT_KEY",
    "github_token": "GITHUB_TOKEN",
    "gitlab_token": "GITLAB_TOKEN",
    "huggingface_token": "HUGGINGFACE_TOKEN",
    "slack_token": "SLACK_TOKEN",
    "stripe_secret_key": "STRIPE_SECRET_KEY",
    "totp_secret": "TOTP_SECRET",
    "recovery_code": "RECOVERY_CODE",
}
BEARER_RE = re.compile(
    r"(?i)\b(authorization\s*:\s*bearer\s+)"
    r"([A-Za-z0-9._~+/=-]{12,})"
)
DSN_PASSWORD_RE = re.compile(
    r"(?i)\b("
    r"(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|"
    r"redis|rediss|amqp|amqps|https?)://"
    r"[^:/@\s]+:"
    r")([^@/\s]+)(?=@)"
)
PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN ([A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?)-----"
    r".*?"
    r"-----END \1-----\n?",
    re.DOTALL,
)
PLACEHOLDER_RE = re.compile(r"\[CREDENTIAL:[A-Z0-9_]+\]")
PROVIDER_PATTERNS = (
    (
        "ANTHROPIC_API_KEY",
        re.compile(r"(?<![A-Za-z0-9])sk-ant-api03-[A-Za-z0-9_-]{40,}(?![A-Za-z0-9])"),
    ),
    (
        "GITHUB_TOKEN",
        re.compile(r"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{40,255})(?![A-Za-z0-9])"),
    ),
    (
        "HUGGINGFACE_TOKEN",
        re.compile(r"(?<![A-Za-z0-9])hf_[A-Za-z0-9]{32,255}(?![A-Za-z0-9])"),
    ),
    (
        "SLACK_TOKEN",
        re.compile(r"(?<![A-Za-z0-9])xox[baprs]-[A-Za-z0-9-]{20,255}(?![A-Za-z0-9])"),
    ),
    (
        "STRIPE_SECRET_KEY",
        re.compile(r"(?<![A-Za-z0-9])sk_(?:live|test)_[A-Za-z0-9]{24,255}(?![A-Za-z0-9])"),
    ),
)
RULE_SET_SHA256 = hashlib.sha256(
    json.dumps(
        {
            "exact_fields": sorted(EXACT_FIELDS.items()),
            "provider_patterns": [
                [credential_class, pattern.pattern]
                for credential_class, pattern in PROVIDER_PATTERNS
            ],
            "embedded_patterns": [
                BEARER_RE.pattern,
                DSN_PASSWORD_RE.pattern,
                PRIVATE_KEY_RE.pattern,
            ],
            "signed_url_schemes": ["aws-sigv4", "azure-sas"],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


class CredentialGateError(RuntimeError):
    """Raised when the credential gate cannot safely transform input."""


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _normalize_field(name: str) -> str:
    return name.strip().casefold().replace(" ", "-")


def _credential_placeholder(credential_class: str) -> str:
    return f"[CREDENTIAL:{credential_class}]"


def _is_placeholder(value: str) -> bool:
    return PLACEHOLDER_RE.fullmatch(value) is not None


def _known_secret_variants(
    credential_class: str,
    secret: str,
) -> list[tuple[str, str]]:
    percent_encoded = "".join(
        character
        if character.isascii() and character.isalnum()
        else f"%{ord(character):02X}"
        for character in secret
    )
    variants = [
        (credential_class, secret),
        (
            f"{credential_class}_URLENCODED",
            percent_encoded,
        ),
        (
            f"{credential_class}_BASE64",
            base64.b64encode(secret.encode("utf-8")).decode("ascii"),
        ),
        (
            f"{credential_class}_BASE64URL",
            base64.urlsafe_b64encode(
                secret.encode("utf-8")
            ).decode("ascii"),
        ),
        (
            f"{credential_class}_HEX",
            secret.encode("utf-8").hex(),
        ),
    ]
    unique: dict[str, str] = {}
    for variant_class, encoded in variants:
        if len(encoded) >= 8 and encoded not in unique:
            unique[encoded] = variant_class
    return [
        (variant_class, encoded)
        for encoded, variant_class in unique.items()
    ]


def _transform_signed_url(
    text: str,
    record: Any,
) -> str:
    """Transform only recognized signed-URL credential parameters."""

    if not (
        text.startswith("https://") or text.startswith("http://")
    ) or any(character.isspace() for character in text):
        return text
    try:
        parts = urlsplit(text)
        query = parse_qsl(
            parts.query,
            keep_blank_values=True,
            strict_parsing=False,
        )
    except ValueError:
        return text
    if not parts.netloc or not query:
        return text

    lower_keys = {key.casefold() for key, _ in query}
    host = (parts.hostname or "").casefold()
    is_aws = (
        "x-amz-algorithm" in lower_keys
        and "x-amz-signature" in lower_keys
    )
    is_azure = (
        host.endswith(".blob.core.windows.net")
        and {"sv", "se", "sig"}.issubset(lower_keys)
    )
    if not is_aws and not is_azure:
        return text

    transformed: list[tuple[str, str]] = []
    for key, child in query:
        normalized = key.casefold()
        replacement: Optional[str] = None
        credential_class: Optional[str] = None
        if is_aws and normalized == "x-amz-signature":
            credential_class = "AWS_SIGNED_URL_SIGNATURE"
        elif is_aws and normalized == "x-amz-credential":
            credential_class = "AWS_SIGNED_URL_CREDENTIAL"
        elif is_aws and normalized == "x-amz-security-token":
            credential_class = "AWS_SESSION_TOKEN"
        elif is_azure and normalized == "sig":
            credential_class = "AZURE_SAS_SIGNATURE"
        if credential_class is not None and not _is_placeholder(child):
            record(credential_class, "signed_url")
            replacement = _credential_placeholder(credential_class)
        transformed.append((key, replacement or child))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(transformed, doseq=True),
            parts.fragment,
        )
    )


def transform_credentials(
    value: Any,
    *,
    boundary: str,
    receipt_hmac_key: bytes,
    scope_ref: str,
    purpose: str,
    known_secrets: Optional[Mapping[str, str]] = None,
) -> tuple[Any, dict[str, Any]]:
    """Return a credential-free deep copy and content-free receipt."""

    if boundary not in BOUNDARIES:
        raise CredentialGateError("unknown credential boundary")
    if not isinstance(receipt_hmac_key, bytes) or len(receipt_hmac_key) < 32:
        raise CredentialGateError(
            "credential receipt HMAC key must be at least 32 bytes"
        )
    if (
        not isinstance(scope_ref, str)
        or not scope_ref
        or len(scope_ref) > 256
        or not isinstance(purpose, str)
        or not purpose
        or len(purpose) > 128
    ):
        raise CredentialGateError("scope and purpose are required")
    counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    secret_snapshot: list[tuple[str, str]] = []
    for credential_class, secret in (known_secrets or {}).items():
        if (
            not isinstance(credential_class, str)
            or re.fullmatch(r"[A-Z0-9_]{1,64}", credential_class) is None
            or not isinstance(secret, str)
            or len(secret) < 8
        ):
            raise CredentialGateError(
                "known secret snapshot entry is invalid"
            )
        secret_snapshot.extend(
            _known_secret_variants(credential_class, secret)
        )
    secret_snapshot.sort(key=lambda item: len(item[1]), reverse=True)

    def record(credential_class: str, tier: str) -> None:
        counts[credential_class] += 1
        tier_counts[tier] += 1

    def transform_text(text: str) -> str:
        def replace_private_key(_match: re.Match[str]) -> str:
            record("PRIVATE_KEY", "embedded_structure")
            return _credential_placeholder("PRIVATE_KEY") + "\n"

        def replace_bearer(match: re.Match[str]) -> str:
            record("BEARER_TOKEN", "embedded_structure")
            return (
                match.group(1)
                + _credential_placeholder("BEARER_TOKEN")
            )

        def replace_dsn_password(match: re.Match[str]) -> str:
            record("DSN_PASSWORD", "embedded_structure")
            return (
                match.group(1)
                + _credential_placeholder("DSN_PASSWORD")
            )

        result = _transform_signed_url(text, record)
        result = PRIVATE_KEY_RE.sub(replace_private_key, result)
        result = BEARER_RE.sub(replace_bearer, result)
        result = DSN_PASSWORD_RE.sub(replace_dsn_password, result)
        for credential_class, pattern in PROVIDER_PATTERNS:
            def replace_provider(
                _match: re.Match[str],
                credential_class: str = credential_class,
            ) -> str:
                record(credential_class, "provider_grammar")
                return _credential_placeholder(credential_class)

            result = pattern.sub(replace_provider, result)
        for credential_class, secret in secret_snapshot:
            occurrences = result.count(secret)
            if occurrences:
                counts[credential_class] += occurrences
                tier_counts["known_secret"] += occurrences
                result = result.replace(
                    secret,
                    _credential_placeholder(credential_class),
                )
        return result

    def transform(item: Any) -> Any:
        if isinstance(item, Mapping):
            result: dict[Any, Any] = {}
            for key, child in item.items():
                if isinstance(key, str):
                    credential_class = EXACT_FIELDS.get(
                        _normalize_field(key)
                    )
                else:
                    credential_class = None
                already_placeholder = (
                    isinstance(child, str)
                    and re.fullmatch(
                        r"\[CREDENTIAL:[A-Z0-9_]+\]",
                        child,
                    )
                    is not None
                )
                if (
                    credential_class is not None
                    and child is not None
                    and not already_placeholder
                ):
                    record(credential_class, "structured_field")
                    result[key] = _credential_placeholder(
                        credential_class
                    )
                else:
                    result[key] = transform(child)
            return result
        if isinstance(item, list):
            return [transform(child) for child in item]
        if isinstance(item, tuple):
            return tuple(transform(child) for child in item)
        if isinstance(item, str):
            return transform_text(item)
        return copy.deepcopy(item)

    input_encoded = _stable_json(value).encode("utf-8")
    clean = transform(value)
    encoded = _stable_json(clean).encode("utf-8")
    receipt_domain = _stable_json(
        {
            "schema_version": SCHEMA_VERSION,
            "scope_ref": scope_ref,
            "purpose": purpose,
            "boundary": boundary,
            "input": _stable_json(value),
        }
    ).encode("utf-8")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "rule_set_sha256": RULE_SET_SHA256,
        "known_secret_snapshot_hmac_sha256": hmac.new(
            receipt_hmac_key,
            _stable_json(secret_snapshot).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest(),
        "scope_ref": scope_ref,
        "purpose": purpose,
        "boundary": boundary,
        "disposition": "transformed" if counts else "pass",
        "transformed_values": sum(counts.values()),
        "counts_by_class": dict(sorted(counts.items())),
        "counts_by_detector_tier": dict(sorted(tier_counts.items())),
        "bytes_before": len(input_encoded),
        "bytes_after": len(encoded),
        "input_hmac_sha256": hmac.new(
            receipt_hmac_key,
            receipt_domain,
            hashlib.sha256,
        ).hexdigest(),
        "clean_output_sha256": hashlib.sha256(encoded).hexdigest(),
    }
    return clean, receipt


def verify_credential_free(
    value: Any,
    *,
    boundary: str,
    receipt_hmac_key: bytes,
    scope_ref: str,
    purpose: str,
    known_secrets: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Fail closed if the exact serialized value would be transformed."""

    clean, receipt = transform_credentials(
        value,
        boundary=boundary,
        receipt_hmac_key=receipt_hmac_key,
        scope_ref=scope_ref,
        purpose=purpose,
        known_secrets=known_secrets,
    )
    if _stable_json(clean) != _stable_json(value):
        raise CredentialGateError(
            "credential candidate survived the final boundary scan"
        )
    return receipt


def _sign_receipt(
    receipt: Mapping[str, Any],
    receipt_hmac_key: bytes,
) -> str:
    return hmac.new(
        receipt_hmac_key,
        (
            "frankengate-credential-receipt\0"
            + _stable_json(receipt)
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def transform_jsonl_snapshot(
    source: pathlib.Path,
    destination: pathlib.Path,
    *,
    receipt_hmac_key: bytes,
    scope_ref: str,
    purpose: str,
    known_secrets: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Create one immutable credential-clean JSONL research snapshot."""

    source = pathlib.Path(source)
    destination = pathlib.Path(destination)
    if source.resolve() == destination.resolve():
        raise CredentialGateError(
            "raw and clean snapshot paths must differ"
        )
    if destination.exists():
        raise CredentialGateError(
            "credential-clean snapshots are immutable"
        )
    if not source.is_file():
        raise CredentialGateError("raw snapshot is not a file")
    if not destination.parent.is_dir():
        raise CredentialGateError(
            "clean snapshot parent does not exist"
        )

    counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    records = 0
    bytes_before = 0
    bytes_after = 0
    output_hash = hashlib.sha256()
    input_commitment = hmac.new(
        receipt_hmac_key,
        (
            "frankengate-credential-snapshot-input\0"
            + scope_ref
            + "\0"
            + purpose
            + "\0"
        ).encode("utf-8"),
        hashlib.sha256,
    )
    secret_snapshot_hmac: Optional[str] = None
    temporary_path: Optional[pathlib.Path] = None
    try:
        with source.open("rb") as raw_file, tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as clean_file:
            temporary_path = pathlib.Path(clean_file.name)
            for line_number, raw_line in enumerate(raw_file, start=1):
                bytes_before += len(raw_line)
                input_commitment.update(raw_line)
                try:
                    record = json.loads(raw_line)
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise CredentialGateError(
                        f"invalid JSONL record at line {line_number}"
                    ) from error
                clean, line_receipt = transform_credentials(
                    record,
                    boundary="capture",
                    receipt_hmac_key=receipt_hmac_key,
                    scope_ref=scope_ref,
                    purpose=purpose,
                    known_secrets=known_secrets,
                )
                verify_credential_free(
                    clean,
                    boundary="capture",
                    receipt_hmac_key=receipt_hmac_key,
                    scope_ref=scope_ref,
                    purpose=purpose,
                    known_secrets=known_secrets,
                )
                if secret_snapshot_hmac is None:
                    secret_snapshot_hmac = line_receipt[
                        "known_secret_snapshot_hmac_sha256"
                    ]
                for credential_class, count in line_receipt[
                    "counts_by_class"
                ].items():
                    counts[credential_class] += count
                for tier, count in line_receipt[
                    "counts_by_detector_tier"
                ].items():
                    tier_counts[tier] += count
                encoded = (
                    _stable_json(clean) + "\n"
                ).encode("utf-8")
                clean_file.write(encoded)
                output_hash.update(encoded)
                bytes_after += len(encoded)
                records += 1
            clean_file.flush()
            os.fsync(clean_file.fileno())
        if records == 0:
            raise CredentialGateError(
                "credential-clean snapshot cannot be empty"
            )
        try:
            os.link(temporary_path, destination)
        except FileExistsError as error:
            raise CredentialGateError(
                "credential-clean snapshots are immutable"
            ) from error
        temporary_path.unlink()
        temporary_path = None
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    unsigned_receipt: dict[str, Any] = {
        "schema_version": (
            "frankengate.credential-clean-snapshot-receipt.v1"
        ),
        "rule_set_sha256": RULE_SET_SHA256,
        "known_secret_snapshot_hmac_sha256": (
            secret_snapshot_hmac
        ),
        "scope_ref": scope_ref,
        "purpose": purpose,
        "boundary": "capture",
        "disposition": (
            "transformed" if counts else "pass"
        ),
        "records": records,
        "transformed_values": sum(counts.values()),
        "counts_by_class": dict(sorted(counts.items())),
        "counts_by_detector_tier": dict(
            sorted(tier_counts.items())
        ),
        "bytes_before": bytes_before,
        "bytes_after": bytes_after,
        "input_hmac_sha256": input_commitment.hexdigest(),
        "clean_output_sha256": output_hash.hexdigest(),
    }
    return {
        **unsigned_receipt,
        "receipt_hmac_sha256": _sign_receipt(
            unsigned_receipt,
            receipt_hmac_key,
        ),
    }


def verify_jsonl_snapshot(
    snapshot: pathlib.Path,
    receipt: Mapping[str, Any],
    *,
    receipt_hmac_key: bytes,
    scope_ref: str,
    purpose: str,
    known_secrets: Optional[Mapping[str, str]] = None,
) -> None:
    """Verify a clean snapshot receipt and rescan every record."""

    if not isinstance(receipt, Mapping):
        raise CredentialGateError("snapshot receipt is invalid")
    unsigned_receipt = dict(receipt)
    signature = unsigned_receipt.pop(
        "receipt_hmac_sha256",
        None,
    )
    if (
        not isinstance(signature, str)
        or not hmac.compare_digest(
            signature,
            _sign_receipt(
                unsigned_receipt,
                receipt_hmac_key,
            ),
        )
    ):
        raise CredentialGateError(
            "snapshot receipt signature mismatch"
        )
    if (
        receipt.get("scope_ref") != scope_ref
        or receipt.get("purpose") != purpose
        or receipt.get("rule_set_sha256") != RULE_SET_SHA256
    ):
        raise CredentialGateError(
            "snapshot authority or rule-set mismatch"
        )

    snapshot_hash = hashlib.sha256()
    records = 0
    try:
        with pathlib.Path(snapshot).open("rb") as clean_file:
            for line_number, raw_line in enumerate(
                clean_file,
                start=1,
            ):
                snapshot_hash.update(raw_line)
                try:
                    record = json.loads(raw_line)
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                ) as error:
                    raise CredentialGateError(
                        "invalid clean JSONL record at line "
                        f"{line_number}"
                    ) from error
                verify_credential_free(
                    record,
                    boundary="capture",
                    receipt_hmac_key=receipt_hmac_key,
                    scope_ref=scope_ref,
                    purpose=purpose,
                    known_secrets=known_secrets,
                )
                records += 1
    except OSError as error:
        raise CredentialGateError(
            "clean snapshot cannot be read"
        ) from error
    if (
        records != receipt.get("records")
        or not hmac.compare_digest(
            snapshot_hash.hexdigest(),
            str(receipt.get("clean_output_sha256", "")),
        )
    ):
        raise CredentialGateError(
            "clean snapshot receipt mismatch"
        )
