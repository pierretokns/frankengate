#!/usr/bin/env python3
"""Validate A2A golden fixtures and provenance manifest."""

import hashlib
import json
import re
import sys
from pathlib import Path

from recoverychecks import run_recovery_checks


BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "fixtures" / "manifest.json"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
CORE_BINDINGS = {"JSONRPC", "HTTP+JSON", "GRPC"}
TASK_STATES = {
    "TASK_STATE_SUBMITTED",
    "TASK_STATE_WORKING",
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_INPUT_REQUIRED",
    "TASK_STATE_REJECTED",
    "TASK_STATE_AUTH_REQUIRED",
}


def load_json(path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(errors, path, message):
    errors.append(f"{path}: {message}")


def require_keys(errors, path, value, keys):
    missing = [key for key in keys if key not in value]
    if missing:
        fail(errors, path, f"missing keys: {', '.join(missing)}")


def validate_source(errors, entry_path, source):
    require_keys(
        errors,
        entry_path,
        source,
        ["repository", "url", "ref", "license", "sourcePath", "sourceSha256"],
    )
    if source.get("license") != "Apache-2.0":
        fail(errors, entry_path, "source license must be Apache-2.0")
    if not HASH_RE.match(source.get("sourceSha256", "")):
        fail(errors, entry_path, "sourceSha256 must be a lowercase SHA-256")
    if not source.get("url", "").startswith(source.get("repository", "")):
        fail(errors, entry_path, "source url must start with repository url")
    for idx, secondary in enumerate(source.get("secondarySources", [])):
        validate_source(errors, f"{entry_path} secondarySources[{idx}]", secondary)


def validate_agent_card(errors, path, data):
    require_keys(errors, path, data, ["name", "version", "supportedInterfaces", "skills"])
    interfaces = data.get("supportedInterfaces")
    if not isinstance(interfaces, list) or not interfaces:
        fail(errors, path, "supportedInterfaces must be a non-empty list")
        return
    seen = set()
    for idx, iface in enumerate(interfaces):
        require_keys(errors, f"{path} supportedInterfaces[{idx}]", iface, ["protocolBinding", "protocolVersion", "url"])
        binding = iface.get("protocolBinding")
        version = iface.get("protocolVersion")
        if binding not in CORE_BINDINGS:
            fail(errors, path, f"unsupported core binding {binding!r}")
        if version != "1.0":
            fail(errors, path, f"agent card fixture only pins v1.0 interfaces, got {version!r}")
        seen.add(binding)
    if seen != CORE_BINDINGS:
        fail(errors, path, "agent card fixture must cover JSONRPC, HTTP+JSON, and GRPC")
    if not data.get("securitySchemes") or not data.get("securityRequirements"):
        fail(errors, path, "agent card fixture must include security schemes and requirements")


def validate_task(errors, path, data):
    require_keys(errors, path, data, ["id", "contextId", "status", "artifacts", "history"])
    status = data.get("status", {})
    if status.get("state") != "TASK_STATE_COMPLETED":
        fail(errors, path, "task fixture must end in TASK_STATE_COMPLETED")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        fail(errors, path, "task fixture must include at least one artifact")
    history = data.get("history")
    if not isinstance(history, list) or len(history) < 2:
        fail(errors, path, "task fixture must include user and agent history messages")


def validate_streaming_event(errors, path, data):
    if data.get("wireFormat") != "server-sent-events":
        fail(errors, path, "stream fixture wireFormat must be server-sent-events")
    if data.get("contentType") != "text/event-stream":
        fail(errors, path, "stream fixture contentType must be text/event-stream")
    events = data.get("events")
    if not isinstance(events, list) or len(events) < 4:
        fail(errors, path, "stream fixture must include at least four events")
        return
    for idx, event in enumerate(events):
        require_keys(errors, f"{path} events[{idx}]", event, ["event", "id", "data"])
        if event.get("event") != "message":
            fail(errors, path, "all stream events must use SSE event=message")
    if events[0].get("data", {}).get("status", {}).get("state") != "TASK_STATE_SUBMITTED":
        fail(errors, path, "first stream event must carry the submitted task")
    if events[-1].get("data", {}).get("status", {}).get("state") != "TASK_STATE_COMPLETED":
        fail(errors, path, "last stream event must complete the task")
    if not any("artifact" in event.get("data", {}) for event in events):
        fail(errors, path, "stream fixture must include an artifact update event")


def validate_artifact(errors, path, data):
    require_keys(errors, path, data, ["artifactId", "name", "parts"])
    parts = data.get("parts")
    if not isinstance(parts, list) or len(parts) < 3:
        fail(errors, path, "artifact fixture must include text, data, and raw parts")
        return
    if not any("text" in part for part in parts):
        fail(errors, path, "artifact fixture missing text part")
    if not any("data" in part for part in parts):
        fail(errors, path, "artifact fixture missing data part")
    if not any("raw" in part for part in parts):
        fail(errors, path, "artifact fixture missing raw part")


def validate_auth_error(errors, path, data):
    require_keys(errors, path, data, ["agentCardSecurity", "httpChallenge", "jsonrpcError"])
    challenge = data.get("httpChallenge", {})
    if challenge.get("status") != 401:
        fail(errors, path, "auth fixture must preserve HTTP 401")
    headers = challenge.get("headers", {})
    if "WWW-Authenticate" not in headers:
        fail(errors, path, "auth fixture must preserve WWW-Authenticate challenge")
    error = data.get("jsonrpcError", {}).get("error", {})
    if not isinstance(error.get("code"), int):
        fail(errors, path, "jsonrpcError.error.code must be an integer")
    state = error.get("data", {}).get("taskStatus", {}).get("state")
    if state != "TASK_STATE_AUTH_REQUIRED":
        fail(errors, path, "auth fixture must carry TASK_STATE_AUTH_REQUIRED")


def validate_version_negotiation(errors, path, data):
    require_keys(errors, path, data, ["clientSupportedInterfaces", "serverSupportedInterfaces", "expectedSelection"])
    expected = data.get("expectedSelection", {})
    require_keys(errors, f"{path} expectedSelection", expected, ["protocolBinding", "protocolVersion", "url"])
    clients = {(item.get("protocolBinding"), item.get("protocolVersion")) for item in data.get("clientSupportedInterfaces", [])}
    servers = {
        (item.get("protocolBinding"), item.get("protocolVersion"), item.get("url"))
        for item in data.get("serverSupportedInterfaces", [])
    }
    expected_key = (expected.get("protocolBinding"), expected.get("protocolVersion"))
    expected_server = (expected.get("protocolBinding"), expected.get("protocolVersion"), expected.get("url"))
    if expected_key not in clients:
        fail(errors, path, "expected selection is not supported by the client")
    if expected_server not in servers:
        fail(errors, path, "expected selection is not advertised by the server")


CASE_VALIDATORS = {
    "agent_card": validate_agent_card,
    "task": validate_task,
    "streaming_event": validate_streaming_event,
    "artifact": validate_artifact,
    "auth_error": validate_auth_error,
    "version_negotiation": validate_version_negotiation,
}


def main():
    errors = []
    manifest = load_json(MANIFEST)
    require_keys(errors, str(MANIFEST), manifest, ["schemaVersion", "observedAt", "licensePolicy", "fixtures"])
    if manifest.get("schemaVersion") != "bifrost.a2a.fixture-manifest.v1":
        fail(errors, str(MANIFEST), "unexpected schemaVersion")

    seen_paths = set()
    for entry in manifest.get("fixtures", []):
        require_keys(errors, str(MANIFEST), entry, ["path", "case", "sha256", "source", "intendedUse"])
        rel = entry.get("path", "")
        fixture_path = BASE / rel
        if not rel.startswith("fixtures/"):
            fail(errors, rel, "fixture path must stay under fixtures/")
        if rel in seen_paths:
            fail(errors, rel, "duplicate fixture path")
        seen_paths.add(rel)
        if not fixture_path.exists():
            fail(errors, rel, "fixture file does not exist")
            continue
        digest = sha256(fixture_path)
        if entry.get("sha256") != digest:
            fail(errors, rel, f"sha256 mismatch: manifest={entry.get('sha256')} actual={digest}")
        if not HASH_RE.match(entry.get("sha256", "")):
            fail(errors, rel, "sha256 must be a lowercase SHA-256")
        validate_source(errors, rel, entry.get("source", {}))
        data = load_json(fixture_path)
        case = entry.get("case")
        validator = CASE_VALIDATORS.get(case)
        if validator is None:
            fail(errors, rel, f"unknown fixture case {case!r}")
        else:
            validator(errors, rel, data)

    fixture_files = {
        f"fixtures/{path.name}"
        for path in (BASE / "fixtures").glob("*.json")
        if path.name != "manifest.json"
    }
    missing_manifest_entries = fixture_files - seen_paths
    if missing_manifest_entries:
        fail(errors, str(MANIFEST), f"fixture files missing from manifest: {sorted(missing_manifest_entries)}")

    recovery_count = 0
    if not errors:
        recovery_count, recovery_errors = run_recovery_checks()
        for error in recovery_errors:
            fail(errors, "recoverychecks", error)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"validated {len(seen_paths)} A2A fixtures and {recovery_count} recovery checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
