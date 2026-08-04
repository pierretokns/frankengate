#!/usr/bin/env python3
"""Audit dataset manifests against the claim they are being used to support.

This is intentionally conservative. Missing evidence produces a fail or proxy
classification; it never infers enterprise outcomes from a convenient dataset
name alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CLAIMS: dict[str, set[str]] = {
    "nl2sql_schema_retrieval": {"task", "gold_sql", "database_fixture"},
    "trace_structure": {"session_or_trajectory", "messages_or_spans", "tool_calls"},
    "friction_recovery": {"session_or_trajectory", "corrections", "tool_calls", "outcome"},
    "skill_improvement": {"session_or_trajectory", "task", "outcome", "environment_state", "intervention", "holdout"},
    "cross_user_similarity": {"user_identity", "session_or_trajectory", "task", "outcome", "holdout"},
    "term_alias_quality": {"text_or_messages", "term_labels", "alias_labels", "scope"},
}


def _flatten(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def observed_capabilities(manifest: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    direct = {str(item).lower() for item in manifest.get("observed_fields", [])}
    for item in direct:
        if any(token in item for token in ("prompt", "message", "content", "text")):
            fields.add("text_or_messages")
            fields.add("messages_or_spans")
        if any(token in item for token in ("trajectory", "session", "conversation", "rollout")):
            fields.add("session_or_trajectory")
        if any(token in item for token in ("tool", "action", "observation", "span")):
            fields.add("tool_calls")
            fields.add("messages_or_spans")
        if any(token in item for token in ("solved", "success", "outcome", "terminal")):
            fields.add("outcome")
        if any(token in item for token in ("task", "question", "query")):
            fields.add("task")
        if any(token in item for token in ("user", "author", "contributor", "owner")):
            fields.add("user_identity")
        if any(token in item for token in ("correction", "feedback", "rewrite", "revision", "retry")):
            fields.add("corrections")
        if any(token in item for token in ("schema", "database", "ddl", "environment")):
            fields.add("environment_state")
    positive_sections = {
        key: manifest.get(key)
        for key in (
            "source_format", "adapter", "source_adapter", "known_scope",
            "replay_classification", "observed_fields", "observed_agent_roles",
            "split_policy", "cohort", "inventory", "verified_aggregate_audit",
        )
        if key in manifest
    }
    text = _flatten(positive_sections)
    source_format = str(manifest.get("source_format", "")).lower()
    adapter = str(manifest.get("adapter", "")).lower()
    replay = manifest.get("replay_classification", {})
    replay_text = _flatten(replay)
    if "gold sql" in source_format or "gold-sql" in text or replay.get("gold_sql_and_database_fixtures_included"):
        fields.update({"task", "gold_sql", "database_fixture"})
    if any(token in source_format for token in ("otel", "trajectory", "rollout", "jsonl session", "claude code")):
        fields.update({"session_or_trajectory", "messages_or_spans"})
    if any(token in text for token in ("real_tool_calls_and_observations", "tool_calls", "tool-calls")):
        fields.add("tool_calls")
    if any(token in text for token in ("success", "solved", "outcome", "semantic_matches")):
        fields.add("outcome")
    if any(token in text for token in ("correction", "reformulation", "retry", "feedback")):
        fields.add("corrections")
    if any(token in text for token in ("environment_reconstructable", "database_snapshot", "ddl", "schema")):
        fields.add("environment_state")
    if any(token in text for token in ("contributors", "user identity", "user_identity")):
        fields.add("user_identity")
    if manifest.get("split_policy") or "holdout" in text or "family-disjoint" in text:
        fields.add("holdout")
    if any(token in text for token in ("intervention", "causal_intervention")) and any(
        value is True for key, value in replay.items() if "intervention" in key or "causal" in key
    ):
        fields.add("intervention")
    if manifest.get("known_scope", {}).get("tool_calls", 0):
        fields.add("tool_calls")
    if manifest.get("known_scope", {}).get("project_session_tree"):
        fields.add("session_or_trajectory")
    return fields


def classify(manifest: dict[str, Any], claim: str) -> dict[str, Any]:
    required = CLAIMS[claim]
    observed = observed_capabilities(manifest)
    missing = sorted(required - observed)
    if not missing:
        level = "direct"
    elif len(missing) <= 2 and claim in {"nl2sql_schema_retrieval", "trace_structure"}:
        level = "proxy_only"
    else:
        level = "mechanics_only"
    return {
        "dataset_id": manifest.get("dataset_id"),
        "dataset_revision": manifest.get("dataset_revision"),
        "claim": claim,
        "level": level,
        "observed": sorted(observed),
        "required": sorted(required),
        "missing": missing,
        "unsupported_claims": manifest.get("unsupported_claims", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-dir", type=Path, default=Path("configs/datasets"))
    parser.add_argument("--claim", choices=sorted(CLAIMS), action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    claims = args.claim or sorted(CLAIMS)
    rows: list[dict[str, Any]] = []
    for path in sorted(args.manifest_dir.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for claim in claims:
            row = classify(manifest, claim)
            row["manifest"] = str(path)
            rows.append(row)
    aggregate = {
        claim: {
            level: sum(row["claim"] == claim and row["level"] == level for row in rows)
            for level in ("direct", "proxy_only", "mechanics_only")
        }
        for claim in claims
    }
    result = {
        "schema_version": "frankengate-dataset-fit-audit-v1",
        "claim_profiles": {claim: sorted(required) for claim, required in CLAIMS.items() if claim in claims},
        "manifest_count": len(list(args.manifest_dir.glob("*.json"))),
        "rows": rows,
        "aggregate": aggregate,
        "rule": "required observations must be present; missing observations lower the claim level",
    }
    result["result_sha256"] = _stable_hash(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_count": result["manifest_count"], "aggregate": aggregate}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
