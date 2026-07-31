#!/usr/bin/env python3
"""Independently verify content-free Defog replay receipts.

This verifier reads a committed aggregate result and an *external* raw audit
directory. It rechecks hashes, task/arm identity, authority and policy receipt
invariants, terminal-tool scheduling, and aggregate-to-raw consistency without
reusing the runner's in-memory receipt objects. It deliberately does not claim
semantic recomputation: that requires reopening the pinned database and gold
queries, which must be reported explicitly rather than inferred from a stored
boolean.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


TERMINAL_TOOLS = {"submit_sql", "abstain"}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: audit record is not an object")
        rows.append(value)
    return rows


def _event(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    matches = [row for row in rows if row.get("event") == name]
    if len(matches) != 1:
        return None
    return matches[0]


def _tool_names(request: dict[str, Any]) -> set[str]:
    return {
        str(tool.get("function", {}).get("name"))
        for tool in request.get("tools", [])
        if isinstance(tool, dict)
    }


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result_bytes = result_path.read_bytes()
    result = json.loads(result_bytes)
    expected = {
        (str(row.get("task_id_sha256")), str(row.get("arm"))): row
        for row in result.get("task_runs", [])
        if isinstance(row, dict)
    }
    files = sorted(raw_dir.rglob("*.jsonl"))
    checks = {
        "result_json_valid": True,
        "raw_files_found": len(files) == len(expected),
        "task_arm_identity": True,
        "raw_hash_matches_result": True,
        "attempt_chain_matches_result": True,
        "authority_and_epoch_invariants": True,
        "no_unauthorized_observations": True,
        "policy_receipt_invariants": True,
        "terminal_tool_schedule": True,
        "terminal_outcome_consistency": True,
    }
    failures: list[str] = []
    matched: set[tuple[str, str]] = set()

    for path in files:
        try:
            rows = _load_jsonl(path)
        except Exception as exc:  # pragma: no cover - defensive audit boundary
            failures.append(f"{path.name}:invalid_jsonl:{type(exc).__name__}")
            continue
        start = _event(rows, "factorial_task_start")
        end = _event(rows, "factorial_task_end")
        if start is None or end is None:
            failures.append(f"{path.name}:missing_unique_start_or_end")
            checks["task_arm_identity"] = False
            continue
        task_id = str(start.get("task_id", ""))
        arm = str(start.get("arm", ""))
        key = (sha256_text(task_id), arm)
        expected_row = expected.get(key)
        if expected_row is None or not path.name.startswith(
            sha256_text(task_id)[:16] + "-"
        ):
            checks["task_arm_identity"] = False
            failures.append(f"{path.name}:task_arm_not_in_result")
            continue
        matched.add(key)
        if sha256_bytes(path.read_bytes()) != expected_row.get("raw_audit_sha256"):
            checks["raw_hash_matches_result"] = False
            failures.append(f"{path.name}:raw_hash_mismatch")
        if end.get("task_id") != task_id or end.get("arm") != arm:
            checks["task_arm_identity"] = False
            failures.append(f"{path.name}:end_identity_mismatch")
        authority = start.get("authority_receipt") or {}
        attempts = end.get("attempt_receipts") or []
        if not authority.get("authority_valid", False) or not end.get(
            "authority_valid", False
        ):
            checks["authority_and_epoch_invariants"] = False
            failures.append(f"{path.name}:authority_invalid")
        if not authority.get("binding_sha256") or not authority.get(
            "epoch_ref_sha256"
        ):
            checks["authority_and_epoch_invariants"] = False
            failures.append(f"{path.name}:authority_receipt_incomplete")
        if end.get("unauthorized_observation", False) or any(
            bool(attempt.get("unauthorized_observation", False))
            for attempt in attempts
            if isinstance(attempt, dict)
        ):
            checks["no_unauthorized_observations"] = False
            failures.append(f"{path.name}:unauthorized_observation")
        chain = sha256_bytes(canonical_json_bytes(attempts))
        if chain != expected_row.get("attempt_receipt_chain_sha256"):
            checks["attempt_chain_matches_result"] = False
            failures.append(f"{path.name}:attempt_chain_mismatch")
        for attempt in attempts:
            if not isinstance(attempt, dict):
                checks["policy_receipt_invariants"] = False
                failures.append(f"{path.name}:non_object_attempt_receipt")
                continue
            status = attempt.get("status")
            accepted = attempt.get("policy_accepted")
            completed = attempt.get("execution_completed")
            if status == "ok" and not (accepted is True and completed is True):
                checks["policy_receipt_invariants"] = False
                failures.append(f"{path.name}:ok_attempt_invariant")
            if status in {"policy_denied", "authority_denied"} and (
                accepted is True or completed is True
            ):
                checks["policy_receipt_invariants"] = False
                failures.append(f"{path.name}:denied_attempt_invariant")

        # Once the controller announces that no SQL attempts remain, every
        # subsequent model request must expose only native terminal tools.
        terminal_state_seen = False
        for row in rows:
            if row.get("event") == "agent_tool_result":
                try:
                    content = json.loads(str(row.get("content", "{}")))
                except json.JSONDecodeError:
                    content = {}
                terminal_state_seen = terminal_state_seen or bool(
                    (content.get("protocol_state") or {}).get(
                        "required_terminal_action", False
                    )
                )
            elif row.get("event") == "model_request" and terminal_state_seen:
                if not _tool_names(row) <= TERMINAL_TOOLS:
                    checks["terminal_tool_schedule"] = False
                    failures.append(f"{path.name}:nonterminal_tool_after_guard")
        fallback_events = [
            row for row in rows if row.get("event") == "terminal_fallback_controller"
        ]
        fallback_used = bool(fallback_events)
        if bool(expected_row.get("terminal_fallback_used")) != fallback_used:
            checks["terminal_outcome_consistency"] = False
            failures.append(f"{path.name}:fallback_flag_mismatch")
        if end.get("outcome", "").startswith("semantic_correct") and not end.get(
            "semantic_correct", False
        ):
            checks["terminal_outcome_consistency"] = False
            failures.append(f"{path.name}:semantic_outcome_mismatch")

    missing = sorted(set(expected) - matched)
    if missing:
        checks["task_arm_identity"] = False
        failures.extend(f"missing_raw:{task}:{arm}" for task, arm in missing)

    security_passed = all(
        checks[name]
        for name in (
            "raw_files_found",
            "task_arm_identity",
            "raw_hash_matches_result",
            "attempt_chain_matches_result",
            "authority_and_epoch_invariants",
            "no_unauthorized_observations",
            "policy_receipt_invariants",
            "terminal_tool_schedule",
            "terminal_outcome_consistency",
        )
    )
    return {
        "schema_version": "frankengate-defog-independent-verification-v1",
        "result_sha256": sha256_bytes(result_bytes),
        "raw_audit_file_count": len(files),
        "expected_task_arm_count": len(expected),
        "checks": checks,
        "security_and_protocol_verification": security_passed,
        "semantic_recomputation": "not_run_without_pinned_database_executor",
        "semantic_claim_authorized": False,
        "failures": failures,
        "raw_content_committed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(
        args.result.resolve(strict=True), args.raw_audit_dir.resolve(strict=True)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["security_and_protocol_verification"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
