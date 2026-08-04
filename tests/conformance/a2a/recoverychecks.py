#!/usr/bin/env python3
"""Offline A2A recovery/conformance checks.

These checks are intentionally self-contained. They exercise the contract Bifrost
must satisfy for Agent Card ingestion, admission, and broker recovery without
calling model providers, remote agents, DNS, or paid inference APIs.
"""

from __future__ import annotations

import copy
import hashlib
import json
import socket
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BASE = Path(__file__).resolve().parent
FIXTURES = BASE / "fixtures"
MANIFEST = FIXTURES / "manifest.json"

MAX_AGENT_CARD_BYTES = 64 * 1024
CARD_TTL_DAYS = 30
MAX_BROKER_RETRIES = 3

APPROVED_PUBLISHERS = {
    "Maxim AI": "https://getmaxim.ai",
}
ALLOWED_DISCOVERY_HOSTS = {
    "example.invalid",
}
DENIED_DISCOVERY_HOSTS = {
    "localhost",
    "metadata",
    "metadata.google.internal",
}

CORE_BINDINGS = {"JSONRPC", "HTTP+JSON", "GRPC"}
TERMINAL_TASK_STATES = {
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_REJECTED",
}
TASK_TRANSITIONS = {
    None: {"TASK_STATE_SUBMITTED"},
    "TASK_STATE_SUBMITTED": {
        "TASK_STATE_WORKING",
        "TASK_STATE_REJECTED",
        "TASK_STATE_AUTH_REQUIRED",
        "TASK_STATE_INPUT_REQUIRED",
        "TASK_STATE_CANCELED",
    },
    "TASK_STATE_WORKING": {
        "TASK_STATE_COMPLETED",
        "TASK_STATE_FAILED",
        "TASK_STATE_CANCELED",
        "TASK_STATE_INPUT_REQUIRED",
        "TASK_STATE_AUTH_REQUIRED",
    },
    "TASK_STATE_INPUT_REQUIRED": {
        "TASK_STATE_WORKING",
        "TASK_STATE_CANCELED",
        "TASK_STATE_FAILED",
    },
    "TASK_STATE_AUTH_REQUIRED": {
        "TASK_STATE_WORKING",
        "TASK_STATE_REJECTED",
        "TASK_STATE_CANCELED",
        "TASK_STATE_FAILED",
    },
    "TASK_STATE_COMPLETED": set(),
    "TASK_STATE_FAILED": set(),
    "TASK_STATE_CANCELED": set(),
    "TASK_STATE_REJECTED": set(),
}


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    provider_attempts: int = 0


@dataclass(frozen=True)
class AdmissionPolicy:
    trusted_card_digests: frozenset[str]
    allowed_tenants: frozenset[str]
    now: date


@dataclass
class EventFoldResult:
    state: str | None = None
    artifact_ids: list[str] | None = None
    duplicate_events: int = 0
    side_effects: int = 0
    quarantined: bool = False
    quarantine_reason: str = ""

    def __post_init__(self) -> None:
        if self.artifact_ids is None:
            self.artifact_ids = []


@dataclass
class BrokerTask:
    state: str = "TASK_STATE_SUBMITTED"
    retries: int = 0

    def transition(self, target_state: str) -> Decision:
        allowed = TASK_TRANSITIONS.get(self.state, set())
        if target_state not in allowed:
            return Decision("deny", f"invalid_transition:{self.state}->{target_state}")
        self.state = target_state
        return Decision("allow", "transition_applied")

    def transient_failure(self) -> Decision:
        if self.state in TERMINAL_TASK_STATES:
            return Decision("deny", f"terminal_state:{self.state}")
        self.retries += 1
        if self.retries >= MAX_BROKER_RETRIES:
            self.state = "TASK_STATE_FAILED"
            return Decision("deny", "retry_limit_exhausted")
        return Decision("retry", "transient_failure")


@contextmanager
def network_forbidden():
    original_socket = socket.socket

    def fail_socket(*_args, **_kwargs):
        raise AssertionError("network access is forbidden in A2A recovery checks")

    socket.socket = fail_socket
    try:
        yield
    finally:
        socket.socket = original_socket


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def canonical_card_digest(card: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(card).encode("utf-8")).hexdigest()


def parse_manifest_date(manifest: dict[str, Any]) -> date:
    return datetime.strptime(manifest["observedAt"], "%Y-%m-%d").date()


def parse_card(raw: bytes) -> tuple[dict[str, Any] | None, str | None]:
    if len(raw) > MAX_AGENT_CARD_BYTES:
        return None, "card_oversized"
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "malformed_json"
    if not isinstance(value, dict):
        return None, "card_not_object"
    return value, None


def card_shape_errors(card: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["name", "version", "supportedInterfaces", "skills"]
    for key in required:
        if key not in card:
            errors.append(f"missing:{key}")

    interfaces = card.get("supportedInterfaces")
    if not isinstance(interfaces, list) or not interfaces:
        errors.append("supportedInterfaces:not_non_empty_list")
    else:
        bindings = set()
        for idx, iface in enumerate(interfaces):
            if not isinstance(iface, dict):
                errors.append(f"supportedInterfaces[{idx}]:not_object")
                continue
            binding = iface.get("protocolBinding")
            version = iface.get("protocolVersion")
            url = iface.get("url")
            if binding not in CORE_BINDINGS:
                errors.append(f"supportedInterfaces[{idx}]:bad_binding")
            if not isinstance(version, str) or not version:
                errors.append(f"supportedInterfaces[{idx}]:bad_version")
            if not isinstance(url, str) or not url:
                errors.append(f"supportedInterfaces[{idx}]:bad_url")
            bindings.add(binding)
        if not CORE_BINDINGS.issubset(bindings):
            errors.append("supportedInterfaces:missing_core_binding")

    skills = card.get("skills")
    if not isinstance(skills, list) or not skills:
        errors.append("skills:not_non_empty_list")
    else:
        for idx, skill in enumerate(skills):
            if not isinstance(skill, dict):
                errors.append(f"skills[{idx}]:not_object")
                continue
            for key in ("id", "name"):
                if not isinstance(skill.get(key), str) or not skill.get(key):
                    errors.append(f"skills[{idx}]:missing_{key}")

    return errors


def is_ip_or_host_forbidden(host: str) -> bool:
    normalized = host.strip("[]").lower()
    if normalized in DENIED_DISCOVERY_HOSTS:
        return True
    try:
        parsed_ip = ip_address(normalized)
    except ValueError:
        return False
    return (
        parsed_ip.is_loopback
        or parsed_ip.is_private
        or parsed_ip.is_link_local
        or parsed_ip.is_multicast
        or parsed_ip.is_reserved
        or parsed_ip.is_unspecified
    )


def validate_public_https_url(raw_url: str, allowed_hosts: set[str]) -> str | None:
    parsed = urlparse(raw_url)
    if parsed.scheme != "https":
        return "unsafe_url_scheme"
    host = parsed.hostname
    if not host:
        return "unsafe_url_missing_host"
    normalized_host = host.lower()
    if is_ip_or_host_forbidden(normalized_host):
        return "unsafe_url_private_host"
    if normalized_host not in allowed_hosts:
        return "unsafe_url_unapproved_host"
    return None


def card_url_errors(card: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    documentation_url = card.get("documentationUrl")
    if isinstance(documentation_url, str):
        reason = validate_public_https_url(documentation_url, ALLOWED_DISCOVERY_HOSTS)
        if reason:
            errors.append(f"documentationUrl:{reason}")

    for idx, iface in enumerate(card.get("supportedInterfaces", [])):
        if not isinstance(iface, dict) or not isinstance(iface.get("url"), str):
            continue
        reason = validate_public_https_url(iface["url"], ALLOWED_DISCOVERY_HOSTS)
        if reason:
            errors.append(f"supportedInterfaces[{idx}].url:{reason}")
    return errors


def trust_decision(card: dict[str, Any], policy: AdmissionPolicy) -> Decision:
    provider = card.get("provider")
    if not isinstance(provider, dict):
        return Decision("quarantine", "publisher_missing")
    org = provider.get("organization")
    url = provider.get("url")
    if not isinstance(org, str) or not isinstance(url, str):
        return Decision("quarantine", "publisher_incomplete")
    if APPROVED_PUBLISHERS.get(org) != url:
        return Decision("quarantine", "publisher_not_approved")
    if not card.get("securitySchemes") or not card.get("securityRequirements"):
        return Decision("quarantine", "security_review_required")
    if canonical_card_digest(card) not in policy.trusted_card_digests:
        return Decision("quarantine", "unapproved_card_digest")
    return Decision("allow", "trusted")


def is_stale(last_seen_at: date, now: date) -> bool:
    return (now - last_seen_at).days > CARD_TTL_DAYS


def admit_card(
    card: dict[str, Any],
    policy: AdmissionPolicy,
    tenant: str,
    requested_binding: str,
    requested_skill_id: str,
    last_seen_at: date,
) -> Decision:
    shape_errors = card_shape_errors(card)
    if shape_errors:
        return Decision("deny", "malformed_card:" + ",".join(shape_errors[:3]))

    url_errors = card_url_errors(card)
    if url_errors:
        return Decision("deny", "ssrf_denied:" + ",".join(url_errors[:3]))

    if is_stale(last_seen_at, policy.now):
        return Decision("deny", "stale_card")

    trust = trust_decision(card, policy)
    if trust.status != "allow":
        return trust

    if tenant not in policy.allowed_tenants:
        return Decision("deny", "tenant_not_allowed")

    if not any(
        iface.get("protocolBinding") == requested_binding for iface in card.get("supportedInterfaces", [])
    ):
        return Decision("deny", "unsupported_interface")

    if not any(skill.get("id") == requested_skill_id for skill in card.get("skills", [])):
        return Decision("deny", "skill_not_allowed")

    return Decision("allow", "admitted")


def admit_raw_card(
    raw: bytes,
    policy: AdmissionPolicy,
    tenant: str,
    requested_binding: str = "JSONRPC",
    requested_skill_id: str = "summarize-task",
    last_seen_at: date | None = None,
) -> Decision:
    card, parse_error = parse_card(raw)
    if parse_error:
        return Decision("deny", parse_error)
    assert card is not None
    return admit_card(
        card,
        policy,
        tenant,
        requested_binding,
        requested_skill_id,
        last_seen_at or policy.now,
    )


def fold_stream_events(events: list[dict[str, Any]]) -> EventFoldResult:
    result = EventFoldResult()
    seen_events: dict[str, str] = {}
    expected_id = 1

    for event in events:
        event_id = str(event.get("id", ""))
        event_fingerprint = canonical_json(event.get("data"))
        if event_id in seen_events:
            if seen_events[event_id] == event_fingerprint:
                result.duplicate_events += 1
                continue
            result.quarantined = True
            result.quarantine_reason = "duplicate_event_conflict"
            return result

        try:
            numeric_id = int(event_id)
        except ValueError:
            result.quarantined = True
            result.quarantine_reason = "non_numeric_event_id"
            return result

        if numeric_id != expected_id:
            result.quarantined = True
            result.quarantine_reason = "out_of_order_event"
            return result

        if result.state in TERMINAL_TASK_STATES:
            result.quarantined = True
            result.quarantine_reason = "event_after_terminal"
            return result

        data = event.get("data")
        if not isinstance(data, dict):
            result.quarantined = True
            result.quarantine_reason = "event_data_not_object"
            return result

        if "status" in data:
            status = data.get("status")
            if not isinstance(status, dict):
                result.quarantined = True
                result.quarantine_reason = "status_not_object"
                return result
            next_state = status.get("state")
            if next_state not in TASK_TRANSITIONS.get(result.state, set()):
                result.quarantined = True
                result.quarantine_reason = f"invalid_transition:{result.state}->{next_state}"
                return result
            result.state = next_state

        if "artifact" in data:
            artifact = data.get("artifact")
            artifact_id = artifact.get("artifactId") if isinstance(artifact, dict) else None
            if not isinstance(artifact_id, str) or not artifact_id:
                result.quarantined = True
                result.quarantine_reason = "artifact_missing_id"
                return result
            if artifact_id not in result.artifact_ids:
                result.artifact_ids.append(artifact_id)
                result.side_effects += 1

        seen_events[event_id] = event_fingerprint
        expected_id += 1

    return result


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_decision(decision: Decision, status: str, reason_prefix: str) -> None:
    expect(decision.status == status, f"expected status {status}, got {decision}")
    expect(
        decision.reason.startswith(reason_prefix),
        f"expected reason prefix {reason_prefix!r}, got {decision.reason!r}",
    )
    expect(decision.provider_attempts == 0, f"provider attempts must stay zero, got {decision}")


class RecoveryHarness:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.count = 0

    def check(self, name: str, fn) -> None:
        self.count += 1
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - report all deterministic failures.
            self.errors.append(f"{name}: {exc}")


def mutated(card: dict[str, Any], mutator) -> dict[str, Any]:
    candidate = copy.deepcopy(card)
    mutator(candidate)
    return candidate


def build_policy(card: dict[str, Any], manifest: dict[str, Any]) -> AdmissionPolicy:
    return AdmissionPolicy(
        trusted_card_digests=frozenset({canonical_card_digest(card)}),
        allowed_tenants=frozenset({"tenant-alpha"}),
        now=parse_manifest_date(manifest),
    )


def run_recovery_checks() -> tuple[int, list[str]]:
    manifest = load_json(MANIFEST)
    card = load_json(FIXTURES / "agent-card.multi-transport.v1.json")
    stream = load_json(FIXTURES / "stream.task-lifecycle-sse.v1.json")
    policy = build_policy(card, manifest)
    harness = RecoveryHarness()

    with network_forbidden():
        harness.check(
            "canonical card structured round trip is stable",
            lambda: expect(
                canonical_json(json.loads(canonical_json(card))) == canonical_json(card),
                "canonical JSON changed after decode/encode",
            ),
        )
        harness.check(
            "canonical card digest survives round trip",
            lambda: expect(
                canonical_card_digest(json.loads(canonical_json(card))) == canonical_card_digest(card),
                "card digest changed after round trip",
            ),
        )
        harness.check(
            "canonical card raw admission succeeds",
            lambda: expect_decision(admit_raw_card(canonical_json(card).encode("utf-8"), policy, "tenant-alpha"), "allow", "admitted"),
        )
        harness.check(
            "malformed JSON card is denied",
            lambda: expect_decision(admit_raw_card(b'{"name":', policy, "tenant-alpha"), "deny", "malformed_json"),
        )
        harness.check(
            "schema-malformed card is denied",
            lambda: expect_decision(
                admit_raw_card(canonical_json({"name": "bad"}).encode("utf-8"), policy, "tenant-alpha"),
                "deny",
                "malformed_card",
            ),
        )
        harness.check(
            "oversized card is denied before admission",
            lambda: expect_decision(
                admit_raw_card(
                    canonical_json(mutated(card, lambda c: c.update({"description": "x" * MAX_AGENT_CARD_BYTES}))).encode("utf-8"),
                    policy,
                    "tenant-alpha",
                ),
                "deny",
                "card_oversized",
            ),
        )

        ssrf_urls = [
            "http://example.invalid/a2a/jsonrpc",
            "https://127.0.0.1/a2a/jsonrpc",
            "https://[::1]/a2a/jsonrpc",
            "https://10.0.0.4/a2a/jsonrpc",
            "https://169.254.169.254/latest/meta-data",
            "https://metadata.google.internal/computeMetadata/v1",
            "file:///etc/passwd",
            "https://evil.example/a2a/jsonrpc",
        ]
        for raw_url in ssrf_urls:
            harness.check(
                f"SSRF fixture URL denied: {raw_url}",
                lambda raw_url=raw_url: expect_decision(
                    admit_card(
                        mutated(card, lambda c, raw_url=raw_url: c["supportedInterfaces"][0].update({"url": raw_url})),
                        policy,
                        "tenant-alpha",
                        "JSONRPC",
                        "summarize-task",
                        policy.now,
                    ),
                    "deny",
                    "ssrf_denied",
                ),
            )

        harness.check(
            "unapproved publisher is quarantined",
            lambda: expect_decision(
                admit_card(
                    mutated(card, lambda c: c["provider"].update({"organization": "Unknown", "url": "https://getmaxim.ai"})),
                    policy,
                    "tenant-alpha",
                    "JSONRPC",
                    "summarize-task",
                    policy.now,
                ),
                "quarantine",
                "publisher_not_approved",
            ),
        )
        harness.check(
            "approved publisher with changed card digest is quarantined",
            lambda: expect_decision(
                admit_card(
                    mutated(card, lambda c: c["skills"].append({"id": "new-skill", "name": "New Skill"})),
                    policy,
                    "tenant-alpha",
                    "JSONRPC",
                    "summarize-task",
                    policy.now,
                ),
                "quarantine",
                "unapproved_card_digest",
            ),
        )
        harness.check(
            "card missing security requirements is quarantined",
            lambda: expect_decision(
                admit_card(
                    mutated(card, lambda c: c.update({"securityRequirements": []})),
                    policy,
                    "tenant-alpha",
                    "JSONRPC",
                    "summarize-task",
                    policy.now,
                ),
                "quarantine",
                "security_review_required",
            ),
        )
        harness.check(
            "tenant admission deny has zero provider attempts",
            lambda: expect_decision(
                admit_card(card, policy, "tenant-beta", "JSONRPC", "summarize-task", policy.now),
                "deny",
                "tenant_not_allowed",
            ),
        )
        harness.check(
            "unsupported binding admission deny has zero provider attempts",
            lambda: expect_decision(
                admit_card(card, policy, "tenant-alpha", "SLIMRPC", "summarize-task", policy.now),
                "deny",
                "unsupported_interface",
            ),
        )
        harness.check(
            "unsupported skill admission deny has zero provider attempts",
            lambda: expect_decision(
                admit_card(card, policy, "tenant-alpha", "JSONRPC", "delete-production", policy.now),
                "deny",
                "skill_not_allowed",
            ),
        )

        harness.check(
            "broker allows submitted to working transition",
            lambda: expect_decision(BrokerTask().transition("TASK_STATE_WORKING"), "allow", "transition_applied"),
        )
        harness.check(
            "broker blocks terminal state resurrection",
            lambda: expect_decision(
                BrokerTask(state="TASK_STATE_COMPLETED").transition("TASK_STATE_WORKING"),
                "deny",
                "invalid_transition",
            ),
        )

        def retry_limit_check() -> None:
            task = BrokerTask(state="TASK_STATE_WORKING")
            expect_decision(task.transient_failure(), "retry", "transient_failure")
            expect_decision(task.transient_failure(), "retry", "transient_failure")
            expect_decision(task.transient_failure(), "deny", "retry_limit_exhausted")
            expect(task.state == "TASK_STATE_FAILED", f"expected failed terminal state, got {task.state}")
            expect_decision(task.transient_failure(), "deny", "terminal_state")

        harness.check("broker retry limit terminates task once", retry_limit_check)

        harness.check(
            "golden stream folds to completed task with one artifact side effect",
            lambda: (
                lambda result: (
                    expect(not result.quarantined, f"stream unexpectedly quarantined: {result.quarantine_reason}"),
                    expect(result.state == "TASK_STATE_COMPLETED", f"expected completed, got {result.state}"),
                    expect(result.artifact_ids == ["artifact-stream-001"], f"unexpected artifacts {result.artifact_ids}"),
                    expect(result.side_effects == 1, f"expected one artifact side effect, got {result.side_effects}"),
                )
            )(fold_stream_events(stream["events"])),
        )

        def duplicate_event_check() -> None:
            events = copy.deepcopy(stream["events"])
            events.insert(3, copy.deepcopy(events[2]))
            result = fold_stream_events(events)
            expect(not result.quarantined, f"duplicate should be idempotent, got {result.quarantine_reason}")
            expect(result.duplicate_events == 1, f"expected one duplicate, got {result.duplicate_events}")
            expect(result.side_effects == 1, f"duplicate artifact side effect applied {result.side_effects} times")

        harness.check("duplicate stream event is idempotent", duplicate_event_check)

        def conflicting_duplicate_check() -> None:
            events = copy.deepcopy(stream["events"])
            conflict = copy.deepcopy(events[2])
            conflict["data"]["artifact"]["artifactId"] = "artifact-conflict"
            events.insert(3, conflict)
            result = fold_stream_events(events)
            expect(result.quarantined, "conflicting duplicate was not quarantined")
            expect(result.quarantine_reason == "duplicate_event_conflict", result.quarantine_reason)
            expect(result.side_effects == 1, f"conflict should not add a second side effect, got {result.side_effects}")

        harness.check("conflicting duplicate stream event is quarantined", conflicting_duplicate_check)

        def out_of_order_check() -> None:
            events = [copy.deepcopy(stream["events"][0]), copy.deepcopy(stream["events"][2])]
            result = fold_stream_events(events)
            expect(result.quarantined, "out-of-order event was not quarantined")
            expect(result.quarantine_reason == "out_of_order_event", result.quarantine_reason)
            expect(result.side_effects == 0, f"out-of-order artifact side effect leaked, got {result.side_effects}")

        harness.check("out-of-order stream event is quarantined before side effects", out_of_order_check)

        def event_after_terminal_check() -> None:
            events = copy.deepcopy(stream["events"])
            after_terminal = copy.deepcopy(events[1])
            after_terminal["id"] = "5"
            events.append(after_terminal)
            result = fold_stream_events(events)
            expect(result.quarantined, "event after terminal state was not quarantined")
            expect(result.quarantine_reason == "event_after_terminal", result.quarantine_reason)

        harness.check("event after terminal state is quarantined", event_after_terminal_check)

        harness.check(
            "fresh card is not stale",
            lambda: expect_decision(
                admit_card(card, policy, "tenant-alpha", "JSONRPC", "summarize-task", policy.now),
                "allow",
                "admitted",
            ),
        )
        harness.check(
            "stale card denies new admission",
            lambda: expect_decision(
                admit_card(card, policy, "tenant-alpha", "JSONRPC", "summarize-task", date(2026, 6, 1)),
                "deny",
                "stale_card",
            ),
        )

    return harness.count, harness.errors


def main() -> int:
    count, errors = run_recovery_checks()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated {count} A2A recovery checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
