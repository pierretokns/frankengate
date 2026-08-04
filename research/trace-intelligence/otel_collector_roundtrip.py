#!/usr/bin/env python3
"""Real OpenTelemetry SDK -> Collector -> file -> canonical round trip.

This E0 arm sends the twelve governed fixtures through the official
OpenTelemetry Go SDK and OTLP/HTTP exporter, a pinned Collector binary, the
Collector file exporter, and the canonical reimport adapter.

Only aggregate measurements are written to Git. The content-minimized SDK
manifest, Collector storage, process logs, and all identifiers live in a
disposable temporary directory.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import collections
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from typing import Any, Iterable

from canonical_projection_e0 import (
    OTEL_ENVELOPE_VERSION,
    OTEL_SCOPE_NAME,
    OTEL_SCOPE_VERSION,
    canonical_to_openinference_otel,
    openinference_otel_to_canonical,
    verify_projection_receipt,
)
from atif_adapter import CANONICAL_VERSION


RESULT_SCHEMA_VERSION = "frankengate-otel-collector-roundtrip-v1"
SDK_MANIFEST_VERSION = "frankengate-otel-sdk-manifest-v1"
COLLECTOR_VERSION = "0.153.0"
COLLECTOR_DISTRIBUTION = "otelcol-contrib"
COLLECTOR_DARWIN_ARM64_ARCHIVE_SHA256 = (
    "3371b4100c56f853e236b8efa4a134516c5ac09183a07e397a2265f4ab61d63f"
)
COLLECTOR_DARWIN_ARM64_BINARY_SHA256 = (
    "e7e443f18b50ee12f03aaa1ca3bbd8269007e089abffca7fa387835b44c62afc"
)
COLLECTOR_RELEASE_URL = (
    "https://github.com/open-telemetry/opentelemetry-collector-releases/"
    "releases/tag/v0.153.0"
)
COLLECTOR_FILE_EXPORTER_URL = (
    "https://github.com/open-telemetry/opentelemetry-collector-contrib/"
    "blob/v0.153.0/exporter/fileexporter/README.md"
)
OTEL_GO_RELEASE_URL = (
    "https://github.com/open-telemetry/opentelemetry-go/releases/tag/v1.43.0"
)
OTEL_GO_VERSION = "1.43.0"
RESOURCE_SCHEMA_URL = "https://opentelemetry.io/schemas/1.43.0"
ALLOWED_SPAN_ATTRIBUTE_KEYS = {
    "openinference.span.kind",
    "frankengate.canonical.event_id",
    "frankengate.canonical.sequence",
    "frankengate.canonical.kind",
    "frankengate.canonical.observation_status",
    "frankengate.canonical.source_role",
    "gen_ai.operation.name",
    "gen_ai.tool.call.id",
    "gen_ai.tool.name",
    "frankengate.attempt",
    "frankengate.projection.receipt_id",
    "frankengate.projection.source_event_count",
}
CONTENT_FIELD_TOKENS = {
    "content",
    "arguments",
    "command",
    "reasoning",
    "prompt",
    "completion",
    "input",
    "output",
}
AUTHORITY_FIELD_TOKENS = {
    "authority",
    "authorization",
    "epoch",
    "subject",
    "principal",
    "classification",
    "scope",
    "purpose",
    "tenant",
    "team",
    "policy",
    "authorized_principals",
}


class RoundTripError(RuntimeError):
    """Raised when a reproducibility or conformance invariant fails."""


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _attributes_to_dict(attributes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in attributes:
        key = item.get("key")
        value = item.get("value")
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        if "stringValue" in value:
            result[key] = value["stringValue"]
        elif "intValue" in value:
            result[key] = int(value["intValue"])
        elif "doubleValue" in value:
            result[key] = float(value["doubleValue"])
        elif "boolValue" in value:
            result[key] = bool(value["boolValue"])
    return result


def _attribute(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        encoded = {"boolValue": value}
    elif isinstance(value, int):
        encoded = {"intValue": str(value)}
    elif isinstance(value, float):
        encoded = {"doubleValue": value}
    else:
        encoded = {"stringValue": str(value)}
    return {"key": key, "value": encoded}


def _normalize_id(value: Any, byte_length: int) -> str:
    if not isinstance(value, str):
        raise RoundTripError("OTLP identifier is not a string")
    lowered = value.lower()
    if len(lowered) == byte_length * 2:
        try:
            bytes.fromhex(lowered)
        except ValueError:
            pass
        else:
            return lowered
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise RoundTripError("OTLP identifier is neither hex nor base64") from error
    if len(decoded) != byte_length:
        raise RoundTripError("OTLP identifier has the wrong length")
    return decoded.hex()


def _normalize_span(span: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(span)
    normalized["traceId"] = _normalize_id(span.get("traceId"), 16)
    normalized["spanId"] = _normalize_id(span.get("spanId"), 8)
    parent = span.get("parentSpanId")
    if parent:
        normalized["parentSpanId"] = _normalize_id(parent, 8)
    for link in normalized.get("links", []):
        link["traceId"] = _normalize_id(link.get("traceId"), 16)
        link["spanId"] = _normalize_id(link.get("spanId"), 8)
    for field in ("startTimeUnixNano", "endTimeUnixNano"):
        normalized[field] = str(normalized[field])
    return normalized


def _primary_edges(canonical: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (str(event["event_id"]), str(event["parent_event_id"]))
        for event in canonical.get("events", [])
        if event.get("parent_event_id") is not None
    }


def _all_values(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for nested in value.values():
            yield from _all_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_values(nested)
    else:
        yield value


def _sensitive_source_field_count(canonical: dict[str, Any]) -> tuple[int, int]:
    content_count = 0
    authority_count = 0

    def walk(value: Any) -> None:
        nonlocal content_count, authority_count
        if isinstance(value, dict):
            for key, nested in value.items():
                lowered = key.lower()
                if any(token in lowered for token in CONTENT_FIELD_TOKENS):
                    if nested is not None:
                        content_count += 1
                if any(token in lowered for token in AUTHORITY_FIELD_TOKENS):
                    if nested is not None:
                        authority_count += 1
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(canonical)
    return content_count, authority_count


def build_sdk_manifest(
    fixtures_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a temporary content-minimized SDK manifest and private oracle."""
    fixture_paths = sorted(fixtures_root.glob("*.json"))
    if not fixture_paths:
        raise RoundTripError("no governed fixtures found")

    manifest_spans: list[dict[str, Any]] = []
    traces: dict[str, dict[str, Any]] = {}
    source_event_count = 0
    source_edge_count = 0
    source_link_count = 0
    source_content_fields = 0
    source_authority_fields = 0
    tool_lifecycle_spans = 0
    authority_event_spans = 0
    receipt_ids: set[str] = set()

    for fixture_path in fixture_paths:
        canonical = json.loads(fixture_path.read_text(encoding="utf-8"))
        projection, receipt = canonical_to_openinference_otel(canonical)
        verify_projection_receipt(canonical, projection, receipt)
        projected = projection["otlp"]["resourceSpans"][0]["scopeSpans"][0][
            "spans"
        ]
        expected_spans: dict[tuple[str, str], dict[str, Any]] = {}
        expected_links: set[tuple[str, str, str, str, str]] = set()
        event_ids = {str(event["event_id"]) for event in canonical["events"]}
        content_fields, authority_fields = _sensitive_source_field_count(
            canonical
        )
        source_content_fields += content_fields
        source_authority_fields += authority_fields
        receipt_ids.add(receipt["receipt_id"])

        trace_hex: str | None = None
        for raw_span in projected:
            span = copy.deepcopy(raw_span)
            trace_hex = _normalize_id(span["traceId"], 16)
            span_hex = _normalize_id(span["spanId"], 8)
            span["statusError"] = span.get("status", {}).get("code") == (
                "STATUS_CODE_ERROR"
            )
            span.pop("status", None)
            span.pop("kind", None)
            span["attributes"].extend(
                [
                    _attribute(
                        "frankengate.projection.receipt_id",
                        receipt["receipt_id"],
                    ),
                    _attribute(
                        "frankengate.projection.source_event_count",
                        len(projected),
                    ),
                ]
            )
            keys = {
                item["key"]
                for item in span["attributes"]
                if isinstance(item, dict) and isinstance(item.get("key"), str)
            }
            forbidden = keys - ALLOWED_SPAN_ATTRIBUTE_KEYS
            if forbidden:
                raise RoundTripError(
                    "SDK manifest contains non-allowlisted span attributes"
                )
            attributes = _attributes_to_dict(span["attributes"])
            kind = str(attributes["frankengate.canonical.kind"])
            if kind.startswith(("tool.", "tool_")):
                tool_lifecycle_spans += 1
            if kind.startswith(
                ("authorization", "governance", "cache_authority")
            ):
                authority_event_spans += 1
            for link in span.get("links", []):
                link_attributes = _attributes_to_dict(
                    link.get("attributes", [])
                )
                expected_links.add(
                    (
                        trace_hex,
                        span_hex,
                        _normalize_id(link["traceId"], 16),
                        _normalize_id(link["spanId"], 8),
                        str(link_attributes["frankengate.relationship"]),
                    )
                )
            expected_spans[(trace_hex, span_hex)] = copy.deepcopy(span)
            manifest_spans.append(span)

        if trace_hex is None:
            raise RoundTripError("fixture projected no spans")
        traces[trace_hex] = {
            "source": canonical,
            "source_event_ids": event_ids,
            "source_edges": _primary_edges(canonical),
            "expected_spans": expected_spans,
            "expected_links": expected_links,
            "receipt_id": receipt["receipt_id"],
        }
        source_event_count += len(canonical["events"])
        source_edge_count += len(_primary_edges(canonical))
        source_link_count += len(expected_links)

    resource_attributes = [
        _attribute("service.name", "frankengate-trace-projection"),
        _attribute(
            "frankengate.canonical.schema_version",
            CANONICAL_VERSION,
        ),
        _attribute("telemetry.sdk.name", "opentelemetry"),
        _attribute("telemetry.sdk.language", "go"),
        _attribute("telemetry.sdk.version", OTEL_GO_VERSION),
        _attribute("frankengate.telemetry.content_included", False),
        _attribute("frankengate.telemetry.authority_values_included", False),
    ]
    manifest = {
        "schemaVersion": SDK_MANIFEST_VERSION,
        "resourceSchemaUrl": RESOURCE_SCHEMA_URL,
        "resourceAttributes": resource_attributes,
        "scopeName": OTEL_SCOPE_NAME,
        "scopeVersion": OTEL_SCOPE_VERSION,
        "spans": manifest_spans,
    }
    oracle = {
        "traces": traces,
        "fixture_count": len(fixture_paths),
        "source_event_count": source_event_count,
        "source_edge_count": source_edge_count,
        "source_link_count": source_link_count,
        "source_content_field_count": source_content_fields,
        "source_authority_field_count": source_authority_fields,
        "tool_lifecycle_span_count": tool_lifecycle_spans,
        "authority_event_span_count": authority_event_spans,
        "receipt_count": len(receipt_ids),
    }
    return manifest, oracle


def load_collector_storage(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise RoundTripError("Collector file exporter produced no storage")
    batches: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError as error:
            raise RoundTripError(
                f"Collector storage line {line_number} is invalid JSON"
            ) from error
        if not isinstance(decoded, dict):
            raise RoundTripError(
                f"Collector storage line {line_number} is not an object"
            )
        batches.append(decoded)
    if not batches:
        raise RoundTripError("Collector storage has no OTLP batches")
    return batches


def _flatten_storage(
    batches: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    resources: list[dict[str, Any]] = []
    scopes: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    for batch in batches:
        resource_spans = batch.get("resourceSpans")
        if not isinstance(resource_spans, list):
            raise RoundTripError("Collector batch lacks resourceSpans")
        for resource_span in resource_spans:
            resources.append(resource_span.get("resource", {}))
            scope_spans = resource_span.get("scopeSpans")
            if not isinstance(scope_spans, list):
                raise RoundTripError("Collector resource lacks scopeSpans")
            for scope_span in scope_spans:
                scopes.append(scope_span.get("scope", {}))
                raw_spans = scope_span.get("spans")
                if not isinstance(raw_spans, list):
                    raise RoundTripError("Collector scope lacks spans")
                spans.extend(_normalize_span(span) for span in raw_spans)
    return resources, scopes, spans


def analyze_roundtrip(
    batches: list[dict[str, Any]],
    oracle: dict[str, Any],
) -> dict[str, Any]:
    resources, scopes, spans = _flatten_storage(batches)
    actual_by_id: dict[tuple[str, str], dict[str, Any]] = {}
    actual_links: set[tuple[str, str, str, str, str]] = set()
    actual_by_trace: dict[str, list[dict[str, Any]]] = collections.defaultdict(
        list
    )
    duplicate_spans = 0
    content_attribute_keys = 0
    authority_attribute_keys = 0
    allowlist_violations = 0
    tool_lifecycle_retained = 0
    authority_event_types_retained = 0
    receipt_pointers_retained = 0
    actual_receipt_ids: set[str] = set()

    for span in spans:
        trace_hex = span["traceId"]
        span_hex = span["spanId"]
        key = (trace_hex, span_hex)
        if key in actual_by_id:
            duplicate_spans += 1
        actual_by_id[key] = span
        actual_by_trace[trace_hex].append(span)
        attrs = _attributes_to_dict(span.get("attributes", []))
        attr_keys = set(attrs)
        allowlist_violations += len(attr_keys - ALLOWED_SPAN_ATTRIBUTE_KEYS)
        content_attribute_keys += sum(
            any(token in key.lower() for token in CONTENT_FIELD_TOKENS)
            for key in attr_keys
        )
        authority_attribute_keys += sum(
            any(token in key.lower() for token in AUTHORITY_FIELD_TOKENS)
            for key in attr_keys
        )
        kind = str(attrs.get("frankengate.canonical.kind", ""))
        if kind.startswith(("tool.", "tool_")):
            if (
                attrs.get("openinference.span.kind") == "TOOL"
                and attrs.get("gen_ai.operation.name") == "execute_tool"
            ):
                tool_lifecycle_retained += 1
        if kind.startswith(
            ("authorization", "governance", "cache_authority")
        ):
            authority_event_types_retained += 1
        receipt_id = attrs.get("frankengate.projection.receipt_id")
        if isinstance(receipt_id, str):
            receipt_pointers_retained += 1
            actual_receipt_ids.add(receipt_id)
        for link in span.get("links", []):
            link_attrs = _attributes_to_dict(link.get("attributes", []))
            actual_links.add(
                (
                    trace_hex,
                    span_hex,
                    link["traceId"],
                    link["spanId"],
                    str(link_attrs.get("frankengate.relationship", "")),
                )
            )

    expected_by_id: dict[tuple[str, str], dict[str, Any]] = {}
    expected_links: set[tuple[str, str, str, str, str]] = set()
    expected_receipt_ids: set[str] = set()
    for trace_oracle in oracle["traces"].values():
        expected_by_id.update(trace_oracle["expected_spans"])
        expected_links.update(trace_oracle["expected_links"])
        expected_receipt_ids.add(trace_oracle["receipt_id"])

    retained_ids = set(expected_by_id) & set(actual_by_id)
    unexpected_ids = set(actual_by_id) - set(expected_by_id)
    missing_ids = set(expected_by_id) - set(actual_by_id)
    expected_trace_ids = {trace_id for trace_id, _ in expected_by_id}
    actual_trace_ids = {trace_id for trace_id, _ in actual_by_id}
    parent_edges_retained = 0
    timestamps_retained = 0
    canonical_attributes_retained = 0
    receipt_identity_matches = 0
    status_retained = 0
    for key in retained_ids:
        expected = expected_by_id[key]
        actual = actual_by_id[key]
        if expected.get("parentSpanId") == actual.get("parentSpanId"):
            if expected.get("parentSpanId") is not None:
                parent_edges_retained += 1
        if (
            str(expected["startTimeUnixNano"])
            == str(actual["startTimeUnixNano"])
            and str(expected["endTimeUnixNano"])
            == str(actual["endTimeUnixNano"])
        ):
            timestamps_retained += 1
        expected_attrs = _attributes_to_dict(expected["attributes"])
        actual_attrs = _attributes_to_dict(actual["attributes"])
        canonical_keys = {
            "frankengate.canonical.event_id",
            "frankengate.canonical.sequence",
            "frankengate.canonical.kind",
            "frankengate.canonical.observation_status",
            "frankengate.canonical.source_role",
        }
        if all(
            actual_attrs.get(attr_key) == expected_attrs.get(attr_key)
            for attr_key in canonical_keys
        ):
            canonical_attributes_retained += 1
        if (
            actual_attrs.get("frankengate.projection.receipt_id")
            == expected_attrs.get("frankengate.projection.receipt_id")
        ):
            receipt_identity_matches += 1
        expected_error = bool(expected.get("statusError"))
        actual_code = actual.get("status", {}).get("code")
        actual_error = actual_code in {"STATUS_CODE_ERROR", 2}
        if expected_error == actual_error:
            status_retained += 1

    reimported_event_count = 0
    reimported_identity_count = 0
    reimported_parent_edges = 0
    reimport_receipt_silent_drops = 0
    trace_event_count_mismatches = 0
    for trace_hex, trace_oracle in oracle["traces"].items():
        trace_spans = actual_by_trace.get(trace_hex, [])
        if trace_spans:
            sample_attrs = _attributes_to_dict(
                trace_spans[0].get("attributes", [])
            )
            expected_count = sample_attrs.get(
                "frankengate.projection.source_event_count"
            )
            if expected_count != len(trace_spans):
                trace_event_count_mismatches += 1
        elif trace_oracle["source_event_ids"]:
            trace_event_count_mismatches += 1
        envelope = {
            "schemaVersion": OTEL_ENVELOPE_VERSION,
            "projectionMetadata": {
                "sourceTraceId": trace_oracle["source"]["trace_id"],
            },
            "otlp": {
                "resourceSpans": [
                    {
                        "resource": {},
                        "scopeSpans": [
                            {
                                "scope": {
                                    "name": OTEL_SCOPE_NAME,
                                    "version": OTEL_SCOPE_VERSION,
                                },
                                "spans": trace_spans,
                            }
                        ],
                    }
                ]
            },
        }
        canonical, receipt = openinference_otel_to_canonical(envelope)
        imported_ids = {
            str(event["event_id"]) for event in canonical.get("events", [])
        }
        reimported_event_count += len(canonical.get("events", []))
        reimported_identity_count += len(
            trace_oracle["source_event_ids"] & imported_ids
        )
        reimported_parent_edges += len(
            trace_oracle["source_edges"] & _primary_edges(canonical)
        )
        reimport_receipt_silent_drops += int(
            receipt.get("silently_dropped_event_count", 0)
        )

    resource_attribute_sets = [
        _attributes_to_dict(resource.get("attributes", []))
        for resource in resources
    ]
    scope_pairs = {
        (scope.get("name"), scope.get("version")) for scope in scopes
    }
    resource_retained = any(
        attrs.get("service.name") == "frankengate-trace-projection"
        and attrs.get("telemetry.sdk.name") == "opentelemetry"
        and attrs.get("telemetry.sdk.language") == "go"
        and attrs.get("telemetry.sdk.version") == OTEL_GO_VERSION
        and attrs.get("frankengate.telemetry.content_included") is False
        and attrs.get(
            "frankengate.telemetry.authority_values_included"
        )
        is False
        for attrs in resource_attribute_sets
    )
    scope_retained = (OTEL_SCOPE_NAME, OTEL_SCOPE_VERSION) in scope_pairs
    result = {
        "collector_batches": len(batches),
        "projected_spans": len(expected_by_id),
        "stored_spans": len(spans),
        "reimported_events": reimported_event_count,
        "trace_ids_projected": len(expected_trace_ids),
        "trace_ids_retained": len(expected_trace_ids & actual_trace_ids),
        "unexpected_trace_ids": len(actual_trace_ids - expected_trace_ids),
        "span_ids_retained": len(retained_ids),
        "unexpected_span_ids": len(unexpected_ids),
        "missing_span_ids": len(missing_ids),
        "duplicate_span_ids": duplicate_spans,
        "canonical_attributes_retained": canonical_attributes_retained,
        "parent_edges_projected": oracle["source_edge_count"],
        "parent_edges_retained": parent_edges_retained,
        "links_projected": len(expected_links),
        "links_retained": len(expected_links & actual_links),
        "unexpected_links": len(actual_links - expected_links),
        "timestamps_retained_exactly": timestamps_retained,
        "statuses_retained": status_retained,
        "tool_lifecycle_spans_projected": oracle[
            "tool_lifecycle_span_count"
        ],
        "tool_lifecycle_semantics_retained": tool_lifecycle_retained,
        "authority_event_types_projected": oracle[
            "authority_event_span_count"
        ],
        "authority_event_types_retained": authority_event_types_retained,
        "source_content_fields_suppressed": oracle[
            "source_content_field_count"
        ],
        "source_authority_fields_suppressed": oracle[
            "source_authority_field_count"
        ],
        "content_attribute_keys_found": content_attribute_keys,
        "authority_attribute_keys_found": authority_attribute_keys,
        "span_attribute_allowlist_violations": allowlist_violations,
        "source_loss_receipts": oracle["receipt_count"],
        "receipt_documents_entering_telemetry": 0,
        "receipt_identities_retained": len(
            expected_receipt_ids & actual_receipt_ids
        ),
        "unexpected_receipt_identities": len(
            actual_receipt_ids - expected_receipt_ids
        ),
        "receipt_identity_pointers_retained": receipt_pointers_retained,
        "receipt_identity_matches": receipt_identity_matches,
        "resource_attributes_retained": resource_retained,
        "instrumentation_scope_retained": scope_retained,
        "reimported_canonical_identities": reimported_identity_count,
        "reimported_parent_edges": reimported_parent_edges,
        "reimport_receipt_silent_drop_count": reimport_receipt_silent_drops,
        "trace_event_count_mismatches": trace_event_count_mismatches,
    }
    result["source_manifest_drop_count"] = len(missing_ids)
    result["all_main_invariants_passed"] = all(
        [
            len(spans) == len(expected_by_id),
            len(expected_trace_ids & actual_trace_ids)
            == len(expected_trace_ids),
            not (actual_trace_ids - expected_trace_ids),
            len(retained_ids) == len(expected_by_id),
            not unexpected_ids,
            duplicate_spans == 0,
            canonical_attributes_retained == len(expected_by_id),
            parent_edges_retained == oracle["source_edge_count"],
            len(expected_links & actual_links) == len(expected_links),
            not (actual_links - expected_links),
            timestamps_retained == len(expected_by_id),
            status_retained == len(expected_by_id),
            tool_lifecycle_retained == oracle["tool_lifecycle_span_count"],
            authority_event_types_retained
            == oracle["authority_event_span_count"],
            content_attribute_keys == 0,
            authority_attribute_keys == 0,
            allowlist_violations == 0,
            receipt_pointers_retained == len(expected_by_id),
            len(expected_receipt_ids & actual_receipt_ids)
            == len(expected_receipt_ids),
            not (actual_receipt_ids - expected_receipt_ids),
            receipt_identity_matches == len(expected_by_id),
            resource_retained,
            scope_retained,
            reimported_identity_count == len(expected_by_id),
            reimported_parent_edges == oracle["source_edge_count"],
            reimport_receipt_silent_drops == 0,
            trace_event_count_mismatches == 0,
        ]
    )
    return result


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_port(process: subprocess.Popen[Any], port: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RoundTripError("Collector exited before OTLP receiver was ready")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.2)
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RoundTripError("Collector OTLP receiver did not become ready")


def _stop_collector(process: subprocess.Popen[Any]) -> int:
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
    try:
        return process.wait(timeout=10)
    except subprocess.TimeoutExpired as error:
        process.terminate()
        process.wait(timeout=5)
        raise RoundTripError("Collector did not shut down after SIGINT") from error


def _run_pipeline(
    *,
    collector: Path,
    config: Path,
    sender: Path,
    manifest_path: Path,
    work_root: Path,
    name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    port = _free_loopback_port()
    output = work_root / f"{name}.otlp.jsonl"
    stdout_path = work_root / f"{name}.collector.stdout.log"
    stderr_path = work_root / f"{name}.collector.stderr.log"
    env = os.environ.copy()
    env["FRANKENGATE_OTEL_LISTEN"] = f"127.0.0.1:{port}"
    env["FRANKENGATE_OTEL_OUTPUT"] = str(output)
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            [str(collector), "--config", str(config)],
            stdout=stdout,
            stderr=stderr,
            env=env,
        )
        try:
            _wait_for_port(process, port)
            sender_run = subprocess.run(
                [
                    str(sender),
                    "--manifest",
                    str(manifest_path),
                    "--endpoint",
                    f"http://127.0.0.1:{port}",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            if sender_run.returncode != 0:
                raise RoundTripError(
                    "OpenTelemetry SDK sender failed during live pipeline: "
                    + sender_run.stderr.strip()[-1000:]
                )
            try:
                sender_summary = json.loads(
                    sender_run.stdout.strip().splitlines()[-1]
                )
            except (IndexError, json.JSONDecodeError) as error:
                raise RoundTripError(
                    "OpenTelemetry SDK sender emitted no valid summary"
                ) from error
            if (
                sender_summary.get("sdk")
                != "go.opentelemetry.io/otel"
                or sender_summary.get("sdk_version") != OTEL_GO_VERSION
                or not isinstance(sender_summary.get("spans_ended"), int)
                or sender_summary.get("spans_ended") <= 0
            ):
                raise RoundTripError(
                    "OpenTelemetry SDK sender summary does not match pins"
                )
            time.sleep(0.3)
        finally:
            collector_exit = _stop_collector(process)
    if collector_exit != 0:
        raise RoundTripError(
            f"Collector exited nonzero after shutdown: {collector_exit}"
        )
    return load_collector_storage(output), {
        "sdk_sender_exit_code": sender_run.returncode,
        "sdk_sender": sender_summary,
        "collector_exit_code": collector_exit,
        "collector_storage_created": output.is_file(),
    }


def _run_unreachable_exporter(sender: Path, manifest_path: Path) -> dict[str, Any]:
    port = _free_loopback_port()
    run = subprocess.run(
        [
            str(sender),
            "--manifest",
            str(manifest_path),
            "--endpoint",
            f"http://127.0.0.1:{port}",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return {
        "sdk_sender_exit_code": run.returncode,
        "failure_detected": run.returncode != 0,
    }


def _collector_identity(collector: Path) -> dict[str, Any]:
    if not collector.is_file():
        raise RoundTripError(f"Collector binary not found: {collector}")
    digest = _sha256_file(collector)
    if digest != COLLECTOR_DARWIN_ARM64_BINARY_SHA256:
        raise RoundTripError(
            "Collector binary SHA-256 does not match pinned darwin/arm64 "
            "release artifact"
        )
    version = subprocess.run(
        [str(collector), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    if f"version {COLLECTOR_VERSION}" not in version:
        raise RoundTripError("Collector version output does not match pin")
    return {
        "distribution": COLLECTOR_DISTRIBUTION,
        "version": COLLECTOR_VERSION,
        "artifact": "otelcol-contrib_0.153.0_darwin_arm64.tar.gz",
        "archive_sha256": COLLECTOR_DARWIN_ARM64_ARCHIVE_SHA256,
        "extracted_binary_sha256": digest,
        "release_url": COLLECTOR_RELEASE_URL,
        "file_exporter_url": COLLECTOR_FILE_EXPORTER_URL,
    }


def run_experiment(
    *,
    fixtures_root: Path,
    collector: Path,
    sender: Path,
    normal_config: Path,
    drop_config: Path,
) -> dict[str, Any]:
    collector_identity = _collector_identity(collector)
    if not sender.is_file():
        raise RoundTripError(f"SDK sender binary not found: {sender}")
    manifest, oracle = build_sdk_manifest(fixtures_root)
    sdk_root = Path(__file__).resolve().parent / "otel-roundtrip-sdk"

    with tempfile.TemporaryDirectory(
        prefix="frankengate-otel-roundtrip-"
    ) as temporary:
        work_root = Path(temporary)
        manifest_path = work_root / "content-minimized-sdk-manifest.json"
        manifest_path.write_text(
            _stable_json(manifest) + "\n", encoding="utf-8"
        )
        main_batches, main_process = _run_pipeline(
            collector=collector,
            config=normal_config,
            sender=sender,
            manifest_path=manifest_path,
            work_root=work_root,
            name="main",
        )
        main = analyze_roundtrip(main_batches, oracle)

        drop_batches, drop_process = _run_pipeline(
            collector=collector,
            config=drop_config,
            sender=sender,
            manifest_path=manifest_path,
            work_root=work_root,
            name="drop-roots",
        )
        drop = analyze_roundtrip(drop_batches, oracle)
        unreachable = _run_unreachable_exporter(sender, manifest_path)

        corrupt = copy.deepcopy(main_batches)
        _, _, corrupt_spans = _flatten_storage(corrupt)
        corrupt_detected = False
        if corrupt_spans:
            corrupt_spans[0]["attributes"] = [
                item
                for item in corrupt_spans[0].get("attributes", [])
                if item.get("key") != "frankengate.canonical.event_id"
            ]
            envelope = {
                "schemaVersion": OTEL_ENVELOPE_VERSION,
                "projectionMetadata": {},
                "otlp": {
                    "resourceSpans": [
                        {
                            "resource": {},
                            "scopeSpans": [
                                {"scope": {}, "spans": [corrupt_spans[0]]}
                            ],
                        }
                    ]
                },
            }
            try:
                openinference_otel_to_canonical(envelope)
            except Exception:
                corrupt_detected = True

        disposable_root = work_root
    raw_paths_absent_after_cleanup = not disposable_root.exists()
    expected_roots = oracle["fixture_count"]
    negative_controls = {
        "collector_filter_drop_roots": {
            "expected_dropped_spans": expected_roots,
            "observed_dropped_spans": drop["missing_span_ids"],
            "source_manifest_detected_drop": drop[
                "source_manifest_drop_count"
            ]
            == expected_roots,
            "per_trace_source_count_detected_drop": drop[
                "trace_event_count_mismatches"
            ]
            == expected_roots,
            "reimport_receipt_alone_detected_upstream_drop": drop[
                "reimport_receipt_silent_drop_count"
            ]
            != 0,
            "important_limitation": (
                "the storage-to-canonical receipt accounts only for spans it "
                "receives; a source manifest or carried expected count is "
                "required to detect Collector-side drops"
            ),
            **drop_process,
        },
        "unreachable_collector": unreachable,
        "corrupt_storage_missing_canonical_identity": {
            "failure_detected": corrupt_detected,
        },
    }
    negative_controls_passed = all(
        [
            negative_controls["collector_filter_drop_roots"][
                "source_manifest_detected_drop"
            ],
            negative_controls["collector_filter_drop_roots"][
                "per_trace_source_count_detected_drop"
            ],
            not negative_controls["collector_filter_drop_roots"][
                "reimport_receipt_alone_detected_upstream_drop"
            ],
            unreachable["failure_detected"],
            corrupt_detected,
        ]
    )
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "completed-real-roundtrip",
        "run_date": "2026-07-30",
        "runtime": {
            "collector": collector_identity,
            "sdk": {
                "name": "go.opentelemetry.io/otel",
                "version": OTEL_GO_VERSION,
                "go_toolchain": main_process["sdk_sender"]["go_toolchain"],
                "go_mod_sha256": _sha256_file(sdk_root / "go.mod"),
                "go_sum_sha256": _sha256_file(sdk_root / "go.sum"),
                "exporter": (
                    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/"
                    "otlptracehttp"
                ),
                "transport": "OTLP/HTTP protobuf over loopback",
                "release_url": OTEL_GO_RELEASE_URL,
            },
            "storage": {
                "exporter": "file",
                "format": "OTLP JSON, one export batch per line",
                "persistence": "disposable local file",
            },
            "configs": {
                "main_sha256": _sha256_file(normal_config),
                "drop_control_sha256": _sha256_file(drop_config),
            },
            "pipeline": (
                "OpenTelemetry Go SDK -> OTLP/HTTP receiver -> batch "
                "processor -> file exporter -> canonical reimport"
            ),
            "main_process": main_process,
        },
        "fixture_corpus": {
            "fixtures": oracle["fixture_count"],
            "canonical_events": oracle["source_event_count"],
            "canonical_parent_edges": oracle["source_edge_count"],
            "projected_links": oracle["source_link_count"],
            "raw_fixtures_or_identifiers_emitted": False,
        },
        "main_roundtrip": main,
        "negative_controls": negative_controls,
        "negative_controls_passed": negative_controls_passed,
        "privacy": {
            "sdk_manifest_content_minimized": True,
            "raw_manifest_storage_and_logs_disposable": True,
            "raw_runtime_paths_emitted": False,
            "raw_runtime_paths_absent_after_cleanup": raw_paths_absent_after_cleanup,
            "aggregate_output_contains_no_fixture_ids_or_content": True,
        },
        "claim_limits": [
            (
                "The run proves retention through the pinned local SDK, "
                "Collector, batch processor, and alpha file exporter; it does "
                "not prove every Collector processor or production backend."
            ),
            (
                "The carried loss-receipt identity and source event count "
                "detect partial per-trace drops, but not a wholly missing "
                "trace without an out-of-band source/export manifest."
            ),
            (
                "Authority event types remain useful for topology, while "
                "authority values and content remain suppressed; telemetry is "
                "not an authorization evidence store."
            ),
            (
                "All fixture timestamps are deterministic reconstructions and "
                "must not be interpreted as observed latency."
            ),
            (
                "The governed fixtures are synthetic conformance cases, not "
                "evidence of production prevalence or enterprise outcomes."
            ),
        ],
    }
    result["all_acceptance_checks_passed"] = bool(
        main["all_main_invariants_passed"] and negative_controls_passed
    )
    return result


def _assert_aggregate_privacy(
    result: dict[str, Any], fixtures_root: Path
) -> None:
    serialized = _stable_json(result)
    for fixture_path in fixtures_root.glob("*.json"):
        source = json.loads(fixture_path.read_text(encoding="utf-8"))
        forbidden = [
            source.get("trace_id"),
            *(
                event.get("event_id")
                for event in source.get("events", [])
            ),
            *(
                value
                for event in source.get("events", [])
                for value in _all_values(event.get("content"))
                if isinstance(value, str) and len(value) >= 8
            ),
        ]
        for value in forbidden:
            if isinstance(value, str) and value and value in serialized:
                raise RoundTripError(
                    "aggregate result contains a fixture identifier or content"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=root / "fixtures" / "governed-v1",
    )
    parser.add_argument("--collector", type=Path, required=True)
    parser.add_argument("--sender", type=Path, required=True)
    parser.add_argument(
        "--normal-config",
        type=Path,
        default=(
            root
            / "configs"
            / "otel"
            / "collector-roundtrip-v0.153.0.yaml"
        ),
    )
    parser.add_argument(
        "--drop-config",
        type=Path,
        default=(
            root
            / "configs"
            / "otel"
            / "collector-drop-v0.153.0.yaml"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        fixtures_root=args.fixtures,
        collector=args.collector,
        sender=args.sender,
        normal_config=args.normal_config,
        drop_config=args.drop_config,
    )
    _assert_aggregate_privacy(result, args.fixtures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
