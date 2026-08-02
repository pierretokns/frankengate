#!/usr/bin/env python3
"""Measure legacy vocabulary/acronym candidate stability on Claude histories.

The input is a local, public Claude Code history export organized as
``.claude/projects/<project>/<session>.jsonl``.  Only aggregate counts and
hashes are written.  The result is a stability diagnostic, not an alias
quality or user-outcome benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from modern_term_acronym_port import acronym_definitions
from term_extraction_gliner_benchmark import deterministic_terms


SCHEMA_VERSION = "frankengate-claude-history-legacy-candidate-stability-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def text_parts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(text_parts(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for key in ("text", "content", "input", "output"):
            if key in value:
                out.extend(text_parts(value[key]))
        return out
    return []


def source_manifest(root: Path) -> tuple[int, int, str]:
    rows: list[tuple[str, int]] = []
    total_bytes = 0
    for path in sorted(root.rglob("*.jsonl")):
        size = path.stat().st_size
        total_bytes += size
        rows.append((str(path.relative_to(root)), size))
    return len(rows), total_bytes, digest(rows)


def load_sessions(root: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    sessions: list[dict[str, Any]] = []
    bad_lines = 0
    for path in sorted(root.rglob("*.jsonl")):
        messages: list[str] = []
        user_messages: list[str] = []
        acronyms: set[tuple[str, str]] = set()
        message_count = 0
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        bad_lines += 1
                        continue
                    message = record.get("message") if isinstance(record, dict) else None
                    if not isinstance(message, dict):
                        continue
                    message_count += 1
                    role = message.get("role")
                    parts = text_parts(message.get("content"))
                    parts = [part for part in parts if part.strip()]
                    if not parts:
                        continue
                    text = "\n".join(parts)
                    messages.append(text)
                    if role == "user":
                        user_messages.append(text)
                        for acronym, candidates in acronym_definitions(text).items():
                            for candidate in candidates:
                                if candidate.get("match") and candidate.get("full_hash"):
                                    acronyms.add((digest(acronym), str(candidate["full_hash"])))
        except OSError:
            continue
        if not messages:
            continue
        project = path.parent.name
        sessions.append(
            {
                "project": project,
                "project_hash": digest(project),
                "session_path": str(path),
                "text": "\n".join(messages),
                "user_messages": user_messages,
                "acronym_pairs": acronyms,
                "message_count": message_count,
            }
        )
    return sessions, {"bad_json_lines": bad_lines}


def run(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    file_count, byte_count, manifest_hash = source_manifest(root)
    sessions, parse_stats = load_sessions(root)
    by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        by_project[session["project"]].append(session)

    project_terms: dict[str, set[str]] = {}
    project_acronyms: dict[str, set[str]] = {}
    project_pairs: dict[str, set[tuple[str, str]]] = {}
    project_rows: list[dict[str, Any]] = []
    for project, rows in sorted(by_project.items()):
        summary = deterministic_terms(
            [{"text": row["text"], "user_messages": row["user_messages"]} for row in rows]
        )
        project_terms[project] = set(summary["top_term_hashes"])
        pairs = set().union(*(row["acronym_pairs"] for row in rows)) if rows else set()
        project_pairs[project] = pairs
        project_acronyms[project] = {acronym for acronym, _ in pairs}
        project_rows.append(
            {
                "project_hash": digest(project),
                "session_count": len(rows),
                "top_term_count": len(project_terms[project]),
                "unique_term_count": summary["unique_term_count"],
                "acronym_pair_count": len(pairs),
                "valid_acronym_count": len(project_acronyms[project]),
                "reformulation_candidate_count": summary["reformulation_candidate_count"],
                "raw_content_committed": False,
            }
        )

    names = sorted(by_project)
    term_frequency: Counter[str] = Counter()
    acronym_frequency: Counter[str] = Counter()
    pair_frequency: Counter[tuple[str, str]] = Counter()
    for project in names:
        term_frequency.update(project_terms[project])
        acronym_frequency.update(project_acronyms[project])
        pair_frequency.update(project_pairs[project])

    jaccards: list[float] = []
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            union = project_terms[left] | project_terms[right]
            jaccards.append(len(project_terms[left] & project_terms[right]) / len(union) if union else 0.0)

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_name": root.name,
            "file_count": file_count,
            "byte_count": byte_count,
            "manifest_sha256": manifest_hash,
            "raw_content_committed": False,
        },
        "coverage": {
            "session_count": len(sessions),
            "project_count": len(names),
            "message_count": sum(row["message_count"] for row in sessions),
            **parse_stats,
        },
        "projects": project_rows,
        "top_term_cohort_frequency": {
            "one_project": sum(value == 1 for value in term_frequency.values()),
            "two_or_more_projects": sum(value >= 2 for value in term_frequency.values()),
            "all_projects": sum(value == len(names) for value in term_frequency.values()),
            "unique_top_hashes": len(term_frequency),
            "pairwise_jaccard_min": round(min(jaccards), 6) if jaccards else 0.0,
            "pairwise_jaccard_median": round(median(jaccards), 6) if jaccards else 0.0,
            "pairwise_jaccard_max": round(max(jaccards), 6) if jaccards else 0.0,
        },
        "acronym_cohort_frequency": {
            "one_project": sum(value == 1 for value in acronym_frequency.values()),
            "two_or_more_projects": sum(value >= 2 for value in acronym_frequency.values()),
            "all_projects": sum(value == len(names) for value in acronym_frequency.values()),
            "unique_valid_acronyms": len(acronym_frequency),
        },
        "definition_pair_cohort_frequency": {
            "one_project": sum(value == 1 for value in pair_frequency.values()),
            "two_or_more_projects": sum(value >= 2 for value in pair_frequency.values()),
            "all_projects": sum(value == len(names) for value in pair_frequency.values()),
            "unique_pairs": len(pair_frequency),
        },
        "claim_boundary": {
            "alias_quality": False,
            "enterprise_concept_quality": False,
            "semantic_equivalence": False,
            "user_outcome": False,
            "reason": "Top-term and parenthetical-definition recurrence measures stability only; shared candidates can be boilerplate and local candidates can be valid private concepts.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": result["coverage"], "terms": result["top_term_cohort_frequency"], "acronyms": result["acronym_cohort_frequency"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
