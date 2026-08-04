#!/usr/bin/env python3
"""Audit public coding-agent histories without emitting their content or identifiers.

The audit distinguishes byte-native session files, scrubbed record-preserving
exports, and flattened derivatives.  Raw strings are inspected only for
structural fields and aggregate redaction/secret-candidate counts.  The result
contains no source paths, native IDs, prompts, tool arguments, or tool results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = "public-native-history-fidelity-result-v1"
ENGINE_VERSION = "public-native-history-fidelity-audit-v1"

SOURCES = {
    "cfahlgren_codex": {
        "dataset_id": "cfahlgren1/codex-sessions",
        "revision": "87dcc5b0df77f94b8750772dce7078866d3e6877",
        "license": "NOASSERTION (Hub metadata: other)",
        "provenance": "public dataset declaring two untouched raw Codex rollouts",
        "representation": "byte_native_codex_rollouts_plus_derived_duplicate_view",
        "home_export_status": "two native Codex session files; not a complete harness home",
    },
    "dataclaw_peter": {
        "dataset_id": "Edmon02/dataclaw-peteromallet",
        "revision": "96e52d19e236676f323cc41916daab006a6ac2e2",
        "license": "MIT",
        "provenance": "public DataClaw mirror/export pointing to Peter O'Malley's source",
        "representation": "flattened_longitudinal_claude_derivative",
        "home_export_status": "normalized conversations; not native Claude files or a complete harness home",
    },
    "jobseek_claude": {
        "dataset_id": "viktor-shcherb/jobseek-agent-traces",
        "revision": "5aae997225724606da9f7d23ada9cd49e81ff177",
        "license": "MIT; publisher tag not-for-AI-training",
        "provenance": "deterministic eight-trace sample from a public workflow corpus",
        "representation": "merged_complete_workflow_claude_derivative",
        "home_export_status": "header plus merged main/subagent records; not a native Claude project tree",
    },
    "mike_codex": {
        "dataset_id": "Mike0021/codex-sessions",
        "revision": "29b52c15654087c5c5d0adcd062bfe40f6464d6b",
        "license": "NOASSERTION",
        "provenance": "public dataset; card declares no license",
        "representation": "scrubbed_record_preserving_codex_derivative",
        "home_export_status": "not a complete Codex harness home",
    },
    "alin_claude": {
        "dataset_id": "AlinCiocan/fable-5-claude-code-traces",
        "revision": "e33ebbca230ae258b2c28aeee9fe3429e7fbeab6",
        "license": "CC-BY-4.0",
        "provenance": "public full-scrubbed release",
        "representation": "scrubbed_native_claude_event_stream",
        "home_export_status": "session files only; not a complete Claude harness home",
    },
    "ranga_codex": {
        "dataset_id": "RangaPrasath/coding-sessions",
        "revision": "9745612dbb84733bd9da15544e7ca8cebaa82c2a",
        "license": "MIT",
        "provenance": "public pi-brain export from Codex session storage",
        "representation": "flattened_redacted_session_derivative",
        "home_export_status": "normalized messages; not native Codex files or a complete harness home",
    },
}


REDACTION_PATTERNS = {
    "literal_redacted": re.compile(
        r"(?:\[REDACTED\]|<REDACTED>|REDACTED_[A-Z0-9_]+)", re.IGNORECASE
    ),
    "numbered_typed_placeholder": re.compile(
        r"<(?:API_KEY|EMAIL|PHONE|IP|PATH|TOKEN|JWT|SECRET|USERNAME|HOST)_\d+>",
        re.IGNORECASE,
    ),
    "scrubbed_typed_placeholder": re.compile(
        r"(?:<|\[)(?:PERSON|DEVICE|HOST|PRIVATE_DOMAIN|PROJECT|MEDIA|PATH|LAN_IP)"
        r"(?:_[A-Z0-9]+)*(?:>|\])",
        re.IGNORECASE,
    ),
}

SECRET_PATTERNS = {
    "openai_or_openrouter_key_candidate": re.compile(
        r"\bsk-(?:proj-|or-)?[A-Za-z0-9_-]{20,}\b"
    ),
    "huggingface_token_candidate": re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    "github_token_candidate": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "aws_access_key_candidate": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "jwt_candidate": re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
    ),
    "private_key_header_candidate": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "bearer_token_candidate": re.compile(
        r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}", re.IGNORECASE
    ),
}


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def iter_strings(value: Any) -> Iterator[str]:
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


class AggregateScanner:
    def __init__(self) -> None:
        self.strings_scanned = 0
        self.redaction_evidence: Counter = Counter()
        self.secret_candidates: Counter = Counter()

    def scan(self, value: Any) -> None:
        for text in iter_strings(value):
            self.strings_scanned += 1
            for name, pattern in REDACTION_PATTERNS.items():
                self.redaction_evidence[name] += len(pattern.findall(text))
            for name, pattern in SECRET_PATTERNS.items():
                for match in pattern.finditer(text):
                    candidate = match.group(0)
                    if "redact" not in candidate.lower():
                        self.secret_candidates[name] += 1

    def aggregate(self) -> Dict[str, Any]:
        return {
            "strings_scanned": self.strings_scanned,
            "redaction_evidence": dict(sorted(self.redaction_evidence.items())),
            "redaction_evidence_total": sum(self.redaction_evidence.values()),
            "possible_secret_regex_candidates": dict(
                sorted(self.secret_candidates.items())
            ),
            "possible_secret_regex_candidate_total": sum(
                self.secret_candidates.values()
            ),
            "candidate_interpretation": (
                "regex candidates only; no values emitted and no validity asserted"
            ),
        }


def parse_jsonl(path: Path) -> Tuple[List[Dict[str, Any]], int, int]:
    rows: List[Dict[str, Any]] = []
    malformed = 0
    blank = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                blank += 1
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(value, dict):
                malformed += 1
                continue
            rows.append(value)
    return rows, malformed, blank


def parseable_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def date_part(value: Any) -> Optional[str]:
    if not parseable_timestamp(value):
        return None
    return str(value)[:10]


def coverage(present: int, eligible: int) -> Dict[str, Any]:
    return {
        "present": present,
        "eligible": eligible,
        "fraction": round(present / eligible, 6) if eligible else None,
    }


def correlation(calls: Mapping[Tuple[str, str], int], results: Mapping[Tuple[str, str], int]) -> Dict[str, int]:
    keys = set(calls).union(results)
    exact_pairs = sum(min(calls.get(key, 0), results.get(key, 0)) for key in keys)
    one_to_one = sum(
        1 for key in keys if calls.get(key, 0) == 1 and results.get(key, 0) == 1
    )
    ambiguous_ids = sum(
        1
        for key in keys
        if calls.get(key, 0) > 1 or results.get(key, 0) > 1
    )
    return {
        "calls_with_id": sum(calls.values()),
        "results_with_id": sum(results.values()),
        "matched_by_id": exact_pairs,
        "one_to_one_id_joins": one_to_one,
        "ambiguous_reused_ids": ambiguous_ids,
        "unresolved_calls": sum(
            max(calls.get(key, 0) - results.get(key, 0), 0) for key in keys
        ),
        "unresolved_results": sum(
            max(results.get(key, 0) - calls.get(key, 0), 0) for key in keys
        ),
    }


def common_result(
    source_key: str,
    *,
    files: int,
    records: int,
    malformed: int,
    blank: int,
    scanner: AggregateScanner,
) -> Dict[str, Any]:
    return {
        "source": SOURCES[source_key],
        "inventory": {
            "jsonl_files": files,
            "valid_records": records,
            "malformed_records": malformed,
            "blank_lines": blank,
        },
        "content_safety_scan": scanner.aggregate(),
        "privacy_contract": {
            "aggregate_counts_only": True,
            "raw_content_emitted": False,
            "native_ids_emitted": False,
            "source_paths_emitted": False,
            "raw_data_committed": False,
        },
    }


def audit_mike(root: Path) -> Dict[str, Any]:
    files = sorted((root / "sessions").glob("*.jsonl"))
    scanner = AggregateScanner()
    records = 0
    malformed = 0
    blank = 0
    record_types: Counter = Counter()
    payload_types: Counter = Counter()
    session_ids = set()
    session_meta = 0
    files_with_multiple_sessions = 0
    timestamp_present = 0
    timestamp_parseable = 0
    record_index_present = 0
    record_index_sequence_violations = 0
    model_records = 0
    usage_records = 0
    thread_source_records = 0
    calls = 0
    results = 0
    per_file_counts: List[Tuple[int, int]] = []

    for path in files:
        rows, bad, empty = parse_jsonl(path)
        malformed += bad
        blank += empty
        records += len(rows)
        local_sessions = set()
        local_calls = 0
        local_results = 0
        expected_index = 0
        for row in rows:
            scanner.scan(row)
            record_type = str(row.get("type", "[missing]"))
            payload = row.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            payload_type = str(payload.get("type", "[missing]"))
            record_types[record_type] += 1
            payload_types[payload_type] += 1
            session_id = row.get("session_id")
            if isinstance(session_id, str):
                session_ids.add(session_id)
                local_sessions.add(session_id)
            if "timestamp" in row:
                timestamp_present += 1
                timestamp_parseable += int(parseable_timestamp(row["timestamp"]))
            if isinstance(row.get("record_index"), int):
                record_index_present += 1
                if row["record_index"] != expected_index:
                    record_index_sequence_violations += 1
                expected_index = row["record_index"] + 1
            if record_type == "session_meta":
                session_meta += 1
                model_records += int(payload.get("model") is not None)
                thread_source_records += int(payload.get("thread_source") is not None)
            if payload_type == "token_count":
                usage_records += 1
            elif payload_type == "function_call":
                calls += 1
                local_calls += 1
            elif payload_type == "function_call_output":
                results += 1
                local_results += 1
        files_with_multiple_sessions += int(len(local_sessions) > 1)
        per_file_counts.append((local_calls, local_results))

    manifest = json.loads((root / "dataset_manifest.json").read_text(encoding="utf-8"))
    result = common_result(
        "mike_codex",
        files=len(files),
        records=records,
        malformed=malformed,
        blank=blank,
        scanner=scanner,
    )
    result.update(
        {
            "inventory": {
                **result["inventory"],
                "distinct_session_ids": len(session_ids),
                "session_meta_records": session_meta,
                "files_with_multiple_session_ids": files_with_multiple_sessions,
                "declared_selected_files": manifest.get("selected_session_count"),
                "declared_published_records": manifest.get(
                    "published_record_count"
                ),
                "actual_minus_declared_records": records
                - int(manifest.get("published_record_count", 0)),
            },
            "record_types": dict(sorted(record_types.items())),
            "payload_types": dict(sorted(payload_types.items())),
            "message_and_tool_structure": {
                "message_records": payload_types["user_message"]
                + payload_types["agent_message"],
                "tool_calls": calls,
                "tool_results": results,
                "call_result_join": {
                    "id_fields_present": False,
                    "exact_id_joins": 0,
                    "order_only_candidate_pairs": sum(
                        min(call_count, result_count)
                        for call_count, result_count in per_file_counts
                    ),
                    "unresolved_call_count_by_cardinality": max(calls - results, 0),
                    "unresolved_result_count_by_cardinality": max(results - calls, 0),
                },
            },
            "fidelity": {
                "timestamp": coverage(timestamp_present, records),
                "parseable_timestamp": coverage(timestamp_parseable, records),
                "record_index": coverage(record_index_present, records),
                "record_index_sequence_violations": record_index_sequence_violations,
                "model_metadata": coverage(model_records, session_meta),
                "usage_metadata_records": usage_records,
                "project_metadata_records": 0,
                "parent_reference_records": 0,
                "branch_points": 0,
                "subagent_or_thread_source_records": thread_source_records,
                "explicit_compaction_records": 0,
            },
            "redaction_manifest": {
                "declared_redactions": manifest.get("redaction_count"),
                "declared_dropped_records": manifest.get("dropped_record_count"),
                "declared_truncated_fields": manifest.get("truncated_field_count"),
            },
            "longitudinal_scope": {
                "stable_user_field": False,
                "explicit_project_field": False,
                "project_proxy_from_file_partition": len(files),
                "human_collaboration_claim_supported": False,
                "autonomous_session_collection": True,
            },
            "loss_receipt": [
                "not byte-native: schema_version, session_id, and record_index were added around Codex records",
                "sanitization changed content and the public card declares no dataset license",
                "function calls and outputs lack call IDs; only order/cardinality pairing is possible",
                "no parent, branch, compaction, stable-user, or explicit project field",
                "27 published files contain more session_meta/session IDs than the file count",
                "actual record count differs from the dataset manifest count",
            ],
        }
    )
    return result


def audit_alin(root: Path) -> Dict[str, Any]:
    files = sorted(root.glob("*.jsonl"))
    scanner = AggregateScanner()
    records = 0
    malformed = 0
    blank = 0
    record_types: Counter = Counter()
    session_ids = set()
    uuids = set()
    parents: Counter = Counter()
    parent_refs = 0
    timestamp_present = 0
    timestamp_parseable = 0
    model_records = 0
    usage_records = 0
    project_records = 0
    calls: Counter = Counter()
    results: Counter = Counter()
    messages = Counter()
    subagent_records = 0
    compaction_records = 0
    attachment_records = 0
    hook_attachment_records = 0
    first_dates: List[str] = []
    last_dates: List[str] = []

    for file_index, path in enumerate(files):
        rows, bad, empty = parse_jsonl(path)
        malformed += bad
        blank += empty
        records += len(rows)
        fallback_scope = f"file-{file_index}"
        for row in rows:
            scanner.scan(row)
            record_type = str(row.get("type", "[missing]"))
            record_types[record_type] += 1
            session_id = row.get("sessionId")
            if isinstance(session_id, str):
                session_ids.add(session_id)
            scope = session_id if isinstance(session_id, str) else fallback_scope
            uuid = row.get("uuid")
            if isinstance(uuid, str):
                uuids.add((scope, uuid))
            parent = row.get("parentUuid")
            if isinstance(parent, str):
                parents[(scope, parent)] += 1
                parent_refs += 1
            timestamp = row.get("timestamp")
            if timestamp is not None:
                timestamp_present += 1
                valid_timestamp = parseable_timestamp(timestamp)
                timestamp_parseable += int(valid_timestamp)
                date = date_part(timestamp)
                if date:
                    first_dates.append(date)
                    last_dates.append(date)
            project_records += int(
                isinstance(row.get("cwd"), str)
                or isinstance(row.get("gitBranch"), str)
            )
            subagent_records += int(
                row.get("isSidechain") is True
                or row.get("sourceToolUseID") is not None
                or row.get("logicalParentUuid") is not None
            )
            compaction_records += int(
                row.get("compactMetadata") is not None
                or row.get("isCompactSummary") is True
            )
            if record_type in {"assistant", "user"}:
                messages[record_type] += 1
                message = row.get("message")
                if isinstance(message, dict):
                    model_records += int(message.get("model") is not None)
                    usage_records += int(message.get("usage") is not None)
                    content = message.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if (
                                block.get("type") == "tool_use"
                                and isinstance(block.get("id"), str)
                            ):
                                calls[(scope, block["id"])] += 1
                                subagent_records += int(block.get("caller") is not None)
                            elif (
                                block.get("type") == "tool_result"
                                and isinstance(block.get("tool_use_id"), str)
                            ):
                                results[(scope, block["tool_use_id"])] += 1
            elif record_type == "attachment":
                attachment_records += 1
                attachment = row.get("attachment")
                if isinstance(attachment, dict):
                    hook_attachment_records += int(
                        str(attachment.get("type", "")).startswith("hook_")
                    )

    parent_joined = sum(
        count for key, count in parents.items() if key in uuids
    )
    dangling = parent_refs - parent_joined
    branch_points = sum(count > 1 for count in parents.values())
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    declared = manifest.get("totals", {})
    result = common_result(
        "alin_claude",
        files=len(files),
        records=records,
        malformed=malformed,
        blank=blank,
        scanner=scanner,
    )
    result.update(
        {
            "inventory": {
                **result["inventory"],
                "distinct_session_ids": len(session_ids),
                "declared_published_files": declared.get("published_files"),
                "declared_published_rows": declared.get("published_rows"),
                "actual_minus_declared_records": records
                - int(declared.get("published_rows", 0)),
            },
            "record_types": dict(sorted(record_types.items())),
            "message_and_tool_structure": {
                "message_records": sum(messages.values()),
                "assistant_records": messages["assistant"],
                "user_records": messages["user"],
                "tool_calls": sum(calls.values()),
                "tool_results": sum(results.values()),
                "call_result_join": correlation(calls, results),
                "attachment_records": attachment_records,
                "hook_attachment_records": hook_attachment_records,
            },
            "fidelity": {
                "timestamp": coverage(timestamp_present, records),
                "parseable_timestamp": coverage(timestamp_parseable, timestamp_present),
                "date_span": {
                    "first_date": min(first_dates) if first_dates else None,
                    "last_date": max(last_dates) if last_dates else None,
                },
                "model_metadata_records": model_records,
                "usage_metadata_records": usage_records,
                "project_metadata_records": project_records,
                "parent_reference_records": parent_refs,
                "parent_references_joined": parent_joined,
                "dangling_parent_references": dangling,
                "branch_points": branch_points,
                "subagent_signal_records": subagent_records,
                "explicit_compaction_records": compaction_records,
            },
            "redaction_manifest": {
                "declared_scrub_operations": declared.get("scrub_total"),
                "declared_excluded_rows": declared.get("excluded_rows"),
                "declared_source_rows": declared.get("source_rows"),
                "deterministic": manifest.get("policy", {}).get("deterministic"),
            },
            "longitudinal_scope": {
                "stable_user_field": False,
                "explicit_project_metadata": project_records > 0,
                "distinct_sessions": len(session_ids),
                "session_files": len(files),
                "single_publisher_context_only": True,
                "cross_user_claim_supported": False,
            },
            "loss_receipt": [
                "record graph is preserved but 35,732 declared scrub operations make it non-byte-native",
                "session events only; Claude settings, skills, memories, credentials, and caches are absent",
                "stable person identity and independently verified task outcomes are absent",
                "hook attachments are operational events, not tool-call results",
            ],
        }
    )
    return result


def audit_ranga(root: Path) -> Dict[str, Any]:
    path = root / "sessions.jsonl"
    rows, malformed, blank = parse_jsonl(path)
    scanner = AggregateScanner()
    sources: Counter = Counter()
    ids_by_source: Dict[str, Counter] = defaultdict(Counter)
    projects = set()
    messages = Counter()
    calls: Counter = Counter()
    results: Counter = Counter()
    timestamp_present = 0
    timestamp_parseable = 0
    model_records = 0
    model_values = set()
    project_records = 0
    message_total = 0
    missing_call_id_tool_messages = 0
    first_dates: List[str] = []
    last_dates: List[str] = []

    for row_index, row in enumerate(rows):
        scanner.scan(row)
        source = str(row.get("source", "[missing]"))
        sources[source] += 1
        native_id = row.get("id")
        if isinstance(native_id, str):
            ids_by_source[source][native_id] += 1
        project = row.get("projectPath")
        if isinstance(project, str):
            project_records += 1
            projects.add(digest(project))
        row_messages = row.get("messages")
        if not isinstance(row_messages, list):
            continue
        scope = f"row-{row_index}"
        for message in row_messages:
            if not isinstance(message, dict):
                continue
            message_total += 1
            role = str(message.get("role", "[missing]"))
            messages[role] += 1
            timestamp = message.get("timestamp")
            if timestamp is not None:
                timestamp_present += 1
                valid_timestamp = parseable_timestamp(timestamp)
                timestamp_parseable += int(valid_timestamp)
                date = date_part(timestamp)
                if date:
                    first_dates.append(date)
                    last_dates.append(date)
            if isinstance(message.get("model"), str):
                model_records += 1
                model_values.add(digest(message["model"]))
            call_id = message.get("toolCallId")
            if isinstance(call_id, str):
                if role == "assistant":
                    calls[(scope, call_id)] += 1
                elif role == "tool-result":
                    results[(scope, call_id)] += 1
            elif message.get("toolName") is not None:
                missing_call_id_tool_messages += 1

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    declared = manifest.get("metadata", {})
    codex_unique = len(ids_by_source.get("codex", {}))
    codex_duplicate_rows = sum(
        max(count - 1, 0) for count in ids_by_source.get("codex", {}).values()
    )
    result = common_result(
        "ranga_codex",
        files=1,
        records=len(rows),
        malformed=malformed,
        blank=blank,
        scanner=scanner,
    )
    result.update(
        {
            "inventory": {
                **result["inventory"],
                "declared_codex_sessions": declared.get("sessionCount"),
                "actual_rows_by_source": dict(sorted(sources.items())),
                "codex_unique_session_ids": codex_unique,
                "codex_duplicate_session_rows": codex_duplicate_rows,
                "declared_codex_messages": declared.get("messageCount"),
                "actual_messages_all_sources": message_total,
                "actual_codex_messages": sum(
                    len(row.get("messages", []))
                    for row in rows
                    if row.get("source") == "codex"
                    and isinstance(row.get("messages"), list)
                ),
            },
            "record_types": {
                "flattened_session_rows": len(rows),
                "message_roles": dict(sorted(messages.items())),
            },
            "message_and_tool_structure": {
                "message_records": message_total,
                "tool_calls": sum(calls.values()),
                "tool_results": sum(results.values()),
                "call_result_join": correlation(calls, results),
                "tool_messages_missing_call_id": missing_call_id_tool_messages,
            },
            "fidelity": {
                "timestamp": coverage(timestamp_present, message_total),
                "parseable_timestamp": coverage(timestamp_parseable, timestamp_present),
                "date_span": {
                    "first_date": min(first_dates) if first_dates else None,
                    "last_date": max(last_dates) if last_dates else None,
                },
                "model_metadata_records": model_records,
                "distinct_model_values": len(model_values),
                "usage_metadata_records": 0,
                "project_metadata_rows": project_records,
                "distinct_project_values": len(projects),
                "parent_reference_records": 0,
                "branch_points": 0,
                "subagent_signal_records": 0,
                "explicit_compaction_records": 0,
            },
            "longitudinal_scope": {
                "stable_user_field": False,
                "dataset_level_single_exporter_inference_only": True,
                "explicit_project_metadata": project_records > 0,
                "cross_user_claim_supported": False,
            },
            "loss_receipt": [
                "pi-brain flattened native Codex records into message rows",
                "system/developer envelopes, record types, parent/branch/subagent/compaction structure, usage, and native ordering metadata are absent",
                "timestamps and project paths were transformed by the declared privacy engine",
                "the file has 73 Codex rows plus 6 OpenCode rows although the card foregrounds 73 Codex sessions",
                "73 Codex rows contain fewer unique Codex session IDs because duplicate session rows are present",
                "tool calls are assistant messages rather than native call objects; some tool messages lack call IDs",
            ],
        }
    )
    return result


def audit_cfahlgren(root: Path) -> Dict[str, Any]:
    files = sorted(root.glob("rollout-*.jsonl"))
    scanner = AggregateScanner()
    records = 0
    malformed = 0
    blank = 0
    record_types: Counter = Counter()
    payload_types: Counter = Counter()
    calls: Counter = Counter()
    results: Counter = Counter()
    timestamps = 0
    parseable_timestamps = 0
    session_meta = 0
    model_records = 0
    project_records = 0
    usage_records = 0
    messages = 0
    raw_text_by_name: Dict[str, str] = {}

    for file_index, path in enumerate(files):
        raw_text_by_name[path.name] = path.read_text(
            encoding="utf-8", errors="replace"
        )
        rows, bad, empty = parse_jsonl(path)
        records += len(rows)
        malformed += bad
        blank += empty
        scope = f"file-{file_index}"
        for row in rows:
            scanner.scan(row)
            record_type = str(row.get("type", "[missing]"))
            payload = row.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            payload_type = str(payload.get("type", "[missing]"))
            record_types[record_type] += 1
            payload_types[payload_type] += 1
            timestamps += int(row.get("timestamp") is not None)
            parseable_timestamps += int(parseable_timestamp(row.get("timestamp")))
            if record_type == "session_meta":
                session_meta += 1
                model_records += int(
                    payload.get("model") is not None
                    or payload.get("model_provider") is not None
                )
                project_records += int(payload.get("cwd") is not None)
            if payload_type == "token_count":
                usage_records += 1
            if payload_type in {"user_message", "agent_message", "message"}:
                messages += 1
            call_id = payload.get("call_id")
            if payload_type == "function_call" and isinstance(call_id, str):
                calls[(scope, call_id)] += 1
            elif payload_type == "function_call_output" and isinstance(
                call_id, str
            ):
                results[(scope, call_id)] += 1

    derived_rows, derived_bad, derived_blank = parse_jsonl(root / "sessions.jsonl")
    exact_derived_matches = 0
    for row in derived_rows:
        file_name = row.get("file_name")
        raw_jsonl = row.get("raw_jsonl")
        if (
            isinstance(file_name, str)
            and isinstance(raw_jsonl, str)
            and raw_text_by_name.get(file_name) == raw_jsonl
        ):
            exact_derived_matches += 1

    result = common_result(
        "cfahlgren_codex",
        files=len(files),
        records=records,
        malformed=malformed,
        blank=blank,
        scanner=scanner,
    )
    result.update(
        {
            "inventory": {
                **result["inventory"],
                "session_meta_records": session_meta,
                "derived_session_rows": len(derived_rows),
                "derived_malformed_rows": derived_bad,
                "derived_blank_lines": derived_blank,
                "derived_rows_byte_equal_to_raw_file": exact_derived_matches,
            },
            "record_types": dict(sorted(record_types.items())),
            "payload_types": dict(sorted(payload_types.items())),
            "message_and_tool_structure": {
                "message_records": messages,
                "tool_calls": sum(calls.values()),
                "tool_results": sum(results.values()),
                "call_result_join": correlation(calls, results),
            },
            "fidelity": {
                "timestamp": coverage(timestamps, records),
                "parseable_timestamp": coverage(parseable_timestamps, timestamps),
                "model_metadata_records": model_records,
                "usage_metadata_records": usage_records,
                "project_metadata_records": project_records,
                "parent_reference_records": 0,
                "branch_points": 0,
                "subagent_signal_records": 0,
                "explicit_compaction_records": 0,
            },
            "longitudinal_scope": {
                "stable_user_field": False,
                "session_files": len(files),
                "explicit_project_metadata": project_records > 0,
                "cross_user_claim_supported": False,
            },
            "loss_receipt": [
                "the two rollout files are byte-native according to the publisher and the derived rows exactly duplicate them",
                "the Hub license is `other`; inspection is permitted but redistribution and training rights are NOASSERTION",
                "the sample is too small for longitudinal, population, or enterprise inference",
                "session files are not a complete Codex harness home",
            ],
        }
    )
    return result


def audit_dataclaw(root: Path) -> Dict[str, Any]:
    rows, malformed, blank = parse_jsonl(root / "conversations.jsonl")
    scanner = AggregateScanner()
    session_ids: Counter = Counter()
    projects = set()
    models = set()
    roles: Counter = Counter()
    messages = 0
    tool_calls = 0
    thinking_records = 0
    timestamp_present = 0
    timestamp_parseable = 0
    first_dates: List[str] = []
    last_dates: List[str] = []
    stats_records = 0

    for row in rows:
        scanner.scan(row)
        session_id = row.get("session_id")
        if isinstance(session_id, str):
            session_ids[session_id] += 1
        project = row.get("project")
        if isinstance(project, str):
            projects.add(digest(project))
        model = row.get("model")
        if isinstance(model, str):
            models.add(digest(model))
        stats_records += int(isinstance(row.get("stats"), dict))
        for boundary in ("start_time", "end_time"):
            date = date_part(row.get(boundary))
            if date:
                first_dates.append(date)
                last_dates.append(date)
        row_messages = row.get("messages")
        if not isinstance(row_messages, list):
            continue
        for message in row_messages:
            if not isinstance(message, dict):
                continue
            messages += 1
            roles[str(message.get("role", "[missing]"))] += 1
            thinking_records += int(message.get("thinking") is not None)
            tool_uses = message.get("tool_uses")
            if isinstance(tool_uses, list):
                tool_calls += len(tool_uses)
            timestamp = message.get("timestamp")
            if timestamp is not None:
                timestamp_present += 1
                timestamp_parseable += int(parseable_timestamp(timestamp))

    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    duplicate_rows = sum(max(count - 1, 0) for count in session_ids.values())
    result = common_result(
        "dataclaw_peter",
        files=1,
        records=len(rows),
        malformed=malformed,
        blank=blank,
        scanner=scanner,
    )
    result.update(
        {
            "inventory": {
                **result["inventory"],
                "declared_sessions": metadata.get("sessions"),
                "unique_session_ids": len(session_ids),
                "duplicate_session_rows": duplicate_rows,
                "declared_projects": len(metadata.get("projects", [])),
                "distinct_project_values": len(projects),
                "declared_skipped_sessions": metadata.get("skipped"),
            },
            "record_types": {
                "flattened_conversation_rows": len(rows),
                "message_roles": dict(sorted(roles.items())),
            },
            "message_and_tool_structure": {
                "message_records": messages,
                "thinking_records": thinking_records,
                "tool_calls_without_native_ids": tool_calls,
                "tool_results": 0,
                "call_result_join": {
                    "id_fields_present": False,
                    "exact_id_joins": 0,
                    "unresolved_calls": tool_calls,
                },
            },
            "fidelity": {
                "timestamp": coverage(timestamp_present, messages),
                "parseable_timestamp": coverage(
                    timestamp_parseable, timestamp_present
                ),
                "date_span": {
                    "first_date": min(first_dates) if first_dates else None,
                    "last_date": max(last_dates) if last_dates else None,
                },
                "model_metadata_rows": len(rows),
                "distinct_model_values": len(models),
                "usage_stats_rows": stats_records,
                "project_metadata_rows": len(rows),
                "parent_reference_records": 0,
                "branch_points": 0,
                "subagent_signal_records": 0,
                "explicit_compaction_records": 0,
            },
            "redaction_manifest": {
                "declared_redactions": metadata.get("redactions"),
                "declared_skipped_sessions": metadata.get("skipped"),
            },
            "longitudinal_scope": {
                "stable_user_field": False,
                "dataset_level_single_user_inference_only": True,
                "explicit_project_metadata": True,
                "cross_user_claim_supported": False,
                "independent_user_cohort": False,
            },
            "loss_receipt": [
                "DataClaw flattened Claude records into conversations and message rows",
                "tool outputs, native tool IDs, parent/branch/subagent/compaction events, permission decisions, and exact event envelopes are absent",
                "549 rows contain fewer unique session IDs because duplicate session rows are present",
                "the repository card points loaders to peteromallet/dataclaw-peteromallet; treat this as a mirror, not an independent user",
                "paths were made project-relative and usernames hashed by the exporter",
            ],
        }
    )
    return result


def audit_jobseek(root: Path) -> Dict[str, Any]:
    files = sorted((root / "traces").glob("*/*.jsonl"))
    scanner = AggregateScanner()
    records = 0
    headers = 0
    malformed = 0
    blank = 0
    declared_records = 0
    record_types: Counter = Counter()
    calls: Counter = Counter()
    results: Counter = Counter()
    uuids = set()
    parents: Counter = Counter()
    timestamp_present = 0
    timestamp_parseable = 0
    model_records = 0
    usage_records = 0
    project_records = 0
    subagent_records = 0
    compaction_records = 0
    messages = 0

    for file_index, path in enumerate(files):
        rows, bad, empty = parse_jsonl(path)
        malformed += bad
        blank += empty
        scope = f"file-{file_index}"
        for row in rows:
            scanner.scan(row)
            if row.get("_trace_header") is True:
                headers += 1
                declared_records += int(row.get("record_count", 0))
                continue
            records += 1
            record_type = str(row.get("type", "[missing]"))
            record_types[record_type] += 1
            uuid = row.get("uuid")
            if isinstance(uuid, str):
                uuids.add((scope, uuid))
            parent = row.get("parentUuid")
            if isinstance(parent, str):
                parents[(scope, parent)] += 1
            timestamp = row.get("timestamp")
            timestamp_present += int(timestamp is not None)
            timestamp_parseable += int(parseable_timestamp(timestamp))
            project_records += int(
                row.get("cwd") is not None or row.get("gitBranch") is not None
            )
            subagent_records += int(
                row.get("isSidechain") is True
                or row.get("agentId") is not None
                or row.get("_agentType") is not None
                or row.get("parentToolUseID") is not None
            )
            compaction_records += int(
                row.get("compactMetadata") is not None
                or row.get("isCompactSummary") is True
            )
            message = row.get("message")
            if record_type in {"assistant", "user"}:
                messages += 1
            if isinstance(message, dict):
                model_records += int(message.get("model") is not None)
                usage_records += int(message.get("usage") is not None)
                content = message.get("content")
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if (
                            block.get("type") == "tool_use"
                            and isinstance(block.get("id"), str)
                        ):
                            calls[(scope, block["id"])] += 1
                        elif (
                            block.get("type") == "tool_result"
                            and isinstance(block.get("tool_use_id"), str)
                        ):
                            results[(scope, block["tool_use_id"])] += 1

    joined_parents = sum(count for key, count in parents.items() if key in uuids)
    parent_refs = sum(parents.values())
    result = common_result(
        "jobseek_claude",
        files=len(files),
        records=records,
        malformed=malformed,
        blank=blank,
        scanner=scanner,
    )
    result.update(
        {
            "inventory": {
                **result["inventory"],
                "header_rows_excluded_from_record_count": headers,
                "declared_records_from_headers": declared_records,
                "actual_minus_declared_records": records - declared_records,
                "sample_scope": "deterministic eight-workflow sample, not the full approximately 5.155 GB corpus",
            },
            "record_types": dict(sorted(record_types.items())),
            "message_and_tool_structure": {
                "message_records": messages,
                "tool_calls": sum(calls.values()),
                "tool_results": sum(results.values()),
                "call_result_join": correlation(calls, results),
            },
            "fidelity": {
                "timestamp": coverage(timestamp_present, records),
                "parseable_timestamp": coverage(
                    timestamp_parseable, timestamp_present
                ),
                "model_metadata_records": model_records,
                "usage_metadata_records": usage_records,
                "project_metadata_records": project_records,
                "parent_reference_records": parent_refs,
                "parent_references_joined_within_merged_file": joined_parents,
                "dangling_parent_references": parent_refs - joined_parents,
                "branch_points": sum(count > 1 for count in parents.values()),
                "subagent_signal_records": subagent_records,
                "explicit_compaction_records": compaction_records,
            },
            "longitudinal_scope": {
                "stable_user_field": False,
                "repeated_single_application_workflow": True,
                "independent_user_cohort": False,
                "cross_user_claim_supported": False,
            },
            "loss_receipt": [
                "each file is a complete workflow derivative with a synthetic header and main/subagent records merged into one chronology",
                "source file-tree and per-agent file boundaries are not preserved",
                "the sample covers eight highly repetitive job-monitor workflows and is not population evidence",
                "publisher metadata says MIT and also not-for-AI-training; this study makes no training-right claim",
                "the full repository was not audited, so counts apply only to the deterministic sample",
            ],
        }
    )
    return result


def wisp_comparator(structural_path: Path, conformance_path: Path) -> Dict[str, Any]:
    structural = json.loads(structural_path.read_text(encoding="utf-8"))
    conformance = json.loads(conformance_path.read_text(encoding="utf-8"))
    coverage_row = structural["coverage"]
    lifecycle = structural["lifecycle"]
    correlation_row = conformance["tool_result_correlation"]
    return {
        "source": conformance["source"],
        "representation": "native Claude project-session tree mirror after credential replacement",
        "home_export_status": "mirrors the Claude project-session directory only; not a complete harness home",
        "inventory": {
            "jsonl_files": coverage_row["jsonl_files"],
            "valid_records": coverage_row["valid_records"],
            "malformed_records": coverage_row["invalid_records"],
            "root_or_main_files": sum(
                coverage_row["files_by_stratum"].get(name, 0)
                for name in ("main_user", "benchmark_development", "benchmark_task")
            ),
            "nested_subagent_files": coverage_row["files_by_stratum"].get(
                "nested_subagent", 0
            ),
        },
        "message_and_tool_structure": {
            "message_records": coverage_row["record_types"].get("assistant", 0)
            + coverage_row["record_types"].get("user", 0),
            "tool_calls": lifecycle["tool_uses"],
            "tool_results": lifecycle["tool_results"],
            "call_result_join": {
                "exact_unique_prior": correlation_row["exact_unique_prior"],
                "unresolved": correlation_row["unresolved"],
            },
        },
        "fidelity": {
            "branch_points": lifecycle["branch_points"],
            "dangling_parent_references": lifecycle[
                "dangling_parent_references"
            ],
            "nested_subagent_files": coverage_row["files_by_stratum"].get(
                "nested_subagent", 0
            ),
        },
        "privacy_contract": conformance["privacy_contract"],
        "loss_receipt": [
            "credential replacement means the mirror is not byte-identical",
            "only the Claude project-session directory is represented; settings, global memory, skills, plugins, credentials, and caches are absent",
            "human-driven, autonomous benchmark, and nested-agent strata must not be merged into one user-behavior cohort",
        ],
    }


def build_result(
    mike_root: Path,
    alin_root: Path,
    ranga_root: Path,
    cfahlgren_root: Path,
    dataclaw_root: Path,
    jobseek_root: Path,
    wisp_structural: Path,
    wisp_conformance: Path,
) -> Dict[str, Any]:
    datasets = {
        "alin_claude": audit_alin(alin_root),
        "cfahlgren_codex": audit_cfahlgren(cfahlgren_root),
        "dataclaw_peter": audit_dataclaw(dataclaw_root),
        "jobseek_claude": audit_jobseek(jobseek_root),
        "mike_codex": audit_mike(mike_root),
        "ranga_codex": audit_ranga(ranga_root),
        "wisp_claude": wisp_comparator(wisp_structural, wisp_conformance),
    }
    result: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "study_scope": {
            "question": "native-history structural fidelity and admission",
            "raw_sources_committed": False,
            "raw_content_or_identifiers_emitted": False,
            "natural_language_semantics_analyzed": False,
            "task_correctness_or_user_skill_measured": False,
        },
        "datasets": datasets,
        "classification": {
            "byte_native_session_files": ["cfahlgren_codex"],
            "actual_native_project_tree": ["wisp_claude"],
            "scrubbed_native_event_stream": ["alin_claude"],
            "record_preserving_normalized_native_derivative": ["mike_codex"],
            "merged_complete_workflow_derivative": ["jobseek_claude"],
            "flattened_session_derivative": [
                "dataclaw_peter",
                "ranga_codex",
            ],
            "complete_harness_home": [],
        },
        "conclusions": [
            "none of the audited datasets is a complete Claude or Codex harness home",
            "Wisp is the closest project-tree mirror and preserves nested subagent files",
            "Alin preserves the richest exact Claude event graph among the newly audited sources",
            "cfahlgren provides the only audited byte-native Codex files, but only two sessions and NOASSERTION rights",
            "Mike preserves Codex record types but cannot exactly join tool calls to results because call IDs are absent",
            "Ranga originates from Codex session storage but is a flattened derivative, not native Codex JSONL",
            "DataClaw provides useful longitudinal coverage but omits tool outputs and is a mirror, not an independent user",
            "Jobseek preserves complete repetitive workflows after merging main and subagent records, not native file boundaries",
            "dataset files, declared counts, native session IDs, and user identities are different quantities",
            "public release does not establish representative enterprise behavior or training rights",
        ],
        "not_proven": [
            "that a session, call, or result was correct",
            "that all rows in a dataset belong to one natural person",
            "employee capability, productivity, skill gap, or collaboration benefit",
            "permission to train on embedded third-party code or outputs",
            "generalization from these public sessions to a governed enterprise",
        ],
    }
    result["result_sha256"] = digest(result)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mike-root", required=True)
    parser.add_argument("--alin-root", required=True)
    parser.add_argument("--ranga-root", required=True)
    parser.add_argument("--cfahlgren-root", required=True)
    parser.add_argument("--dataclaw-root", required=True)
    parser.add_argument("--jobseek-root", required=True)
    parser.add_argument(
        "--wisp-structural",
        default="experiments/results/wisp-longitudinal-structural-pilot-2026-07-30.json",
    )
    parser.add_argument(
        "--wisp-conformance",
        default="experiments/results/wisp-canonical-adapter-conformance-2026-07-30.json",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = build_result(
        Path(args.mike_root),
        Path(args.alin_root),
        Path(args.ranga_root),
        Path(args.cfahlgren_root),
        Path(args.dataclaw_root),
        Path(args.jobseek_root),
        Path(args.wisp_structural),
        Path(args.wisp_conformance),
    )
    with Path(args.output).open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
