#!/usr/bin/env python3
"""Find cross-project surface-term collisions in Claude histories.

This is a lexical hard-negative diagnostic.  It selects the same top-100
termhood candidates used by the legacy stability probe, then compares the
hashed lexical context surrounding each term in each project.  No term,
project, path, message, or context string is emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any


SCHEMA_VERSION = "frankengate-claude-history-term-context-collisions-v1"
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_./:-]{2,}")
STOP = frozenset(
    "the and for with that this from into have what when where which please need want use could would should about then than your you our their there just also does how".split()
)
TOP_TERMS = 100
CONTEXT_CAP = 256


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def token_list(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text) if token.lower() not in STOP and len(token) > 3]


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


def iter_project_messages(root: Path):
    for path in sorted(root.rglob("*.jsonl")):
        project = path.parent.name
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = record.get("message") if isinstance(record, dict) else None
                    if not isinstance(message, dict):
                        continue
                    parts = [part for part in text_parts(message.get("content")) if part.strip()]
                    if parts:
                        yield project, str(path), "\n".join(parts)
        except OSError:
            continue


def file_manifest(root: Path) -> tuple[int, int, str]:
    rows: list[tuple[str, int]] = []
    total = 0
    for path in sorted(root.rglob("*.jsonl")):
        size = path.stat().st_size
        total += size
        rows.append((str(path.relative_to(root)), size))
    return len(rows), total, digest(rows)


def first_pass(root: Path) -> tuple[dict[str, set[str]], dict[str, int], int]:
    document_frequency: dict[str, Counter[str]] = defaultdict(Counter)
    term_frequency: dict[str, Counter[str]] = defaultdict(Counter)
    document_count: Counter[str] = Counter()
    message_count = 0
    current_project: str | None = None
    current_session: str | None = None
    current_terms: list[str] = []
    for project, session, text in iter_project_messages(root):
        message_count += 1
        if session != current_session:
            if current_project is not None:
                document_count[current_project] += 1
                document_frequency[current_project].update(set(current_terms))
                term_frequency[current_project].update(current_terms)
            current_project = project
            current_session = session
            current_terms = []
        current_terms.extend(token_list(text))
    if current_project is not None:
        document_count[current_project] += 1
        document_frequency[current_project].update(set(current_terms))
        term_frequency[current_project].update(current_terms)
    selected: dict[str, set[str]] = {}
    for project, counts in document_frequency.items():
        frequencies = term_frequency[project]
        terms = sorted(counts, key=lambda term: (-counts[term], -frequencies[term], term))[:TOP_TERMS]
        selected[project] = set(terms)
    return selected, dict(document_count), message_count


def second_pass(root: Path, selected: dict[str, set[str]]) -> dict[str, Counter[str]]:
    contexts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for project, _, text in iter_project_messages(root):
        tokens = token_list(text)
        terms = selected.get(project, set())
        if not terms or not tokens:
            continue
        for index, term in enumerate(tokens):
            if term not in terms:
                continue
            left = max(0, index - 4)
            right = min(len(tokens), index + 5)
            for neighbor in tokens[left:index] + tokens[index + 1 : right]:
                if neighbor != term:
                    contexts[project][term][neighbor] += 1
    flattened: dict[str, Counter[str]] = {}
    for project, terms in contexts.items():
        for term, counter in terms.items():
            key = f"{project}\x00{term}"
            flattened[key] = Counter(dict(counter.most_common(CONTEXT_CAP)))
    return flattened


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, max(0, math.floor(fraction * (len(values) - 1))))
    return round(values[index], 6)


def run(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    file_count, byte_count, manifest_hash = file_manifest(root)
    selected, document_counts, first_pass_messages = first_pass(root)
    contexts = second_pass(root, selected)

    projects_by_term: dict[str, set[str]] = defaultdict(set)
    for project, terms in selected.items():
        for term in terms:
            projects_by_term[term].add(project)

    context_sets: dict[tuple[str, str], set[str]] = {}
    for key, counter in contexts.items():
        project, term = key.split("\x00", 1)
        context_sets[(project, term)] = {digest(value) for value in counter}

    pair_values: list[float] = []
    term_pair_values: dict[str, list[float]] = defaultdict(list)
    collision_terms = 0
    ambiguous_terms = 0
    pairs_with_context = 0
    for term, projects in projects_by_term.items():
        if len(projects) < 2:
            continue
        ambiguous_terms += 1
        term_values: list[float] = []
        project_list = sorted(projects)
        for index, left in enumerate(project_list):
            for right in project_list[index + 1 :]:
                left_context = context_sets.get((left, term), set())
                right_context = context_sets.get((right, term), set())
                if not left_context or not right_context:
                    continue
                value = jaccard(left_context, right_context)
                term_values.append(value)
                pair_values.append(value)
                term_pair_values[term].append(value)
                pairs_with_context += 1
        if term_values and min(term_values) < 0.05:
            collision_terms += 1

    threshold_sweep = {}
    for threshold in (0.01, 0.05, 0.10, 0.20, 0.50):
        key = f"{threshold:.2f}"
        threshold_sweep[key] = {
            "pair_count_below": sum(value < threshold for value in pair_values),
            "pair_rate_below": round(sum(value < threshold for value in pair_values) / len(pair_values), 6) if pair_values else 0.0,
            "term_count_with_any_pair_below": sum(any(value < threshold for value in values) for values in term_pair_values.values()),
            "term_rate_with_any_pair_below": round(sum(any(value < threshold for value in values) for values in term_pair_values.values()) / len(term_pair_values), 6) if term_pair_values else 0.0,
        }

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_name": root.name,
            "file_count": file_count,
            "byte_count": byte_count,
            "manifest_sha256": manifest_hash,
            "raw_content_committed": False,
        },
        "protocol": {
            "top_terms_per_project": TOP_TERMS,
            "context_window_tokens": 4,
            "context_cap": CONTEXT_CAP,
            "collision_threshold_jaccard": 0.05,
            "term_selection": "project-local document-frequency top terms",
            "context_similarity": "Jaccard over hashed top lexical neighbor tokens",
        },
        "coverage": {
            "project_count": len(selected),
            "message_count_first_pass": first_pass_messages,
            "selected_term_hash_count": len({digest(term) for terms in selected.values() for term in terms}),
            "shared_term_hash_count": len({digest(term) for term, projects in projects_by_term.items() if len(projects) >= 2}),
            "shared_term_count_with_context_pairs": sum(1 for term, projects in projects_by_term.items() if len(projects) >= 2 and any((project, term) in context_sets for project in projects)),
            "context_pair_count": pairs_with_context,
        },
        "collision_summary": {
            "shared_terms_with_context": ambiguous_terms,
            "terms_with_any_pair_below_0.05": collision_terms,
            "term_collision_rate": round(collision_terms / ambiguous_terms, 6) if ambiguous_terms else 0.0,
            "pair_jaccard_min": quantile(pair_values, 0.0),
            "pair_jaccard_p10": quantile(pair_values, 0.10),
            "pair_jaccard_median": quantile(pair_values, 0.50),
            "pair_jaccard_p90": quantile(pair_values, 0.90),
            "pair_jaccard_max": quantile(pair_values, 1.0),
            "pairs_below_0.05": sum(value < 0.05 for value in pair_values),
            "pairs_at_least_0.50": sum(value >= 0.50 for value in pair_values),
            "threshold_sweep": threshold_sweep,
        },
        "claim_boundary": {
            "semantic_collision": False,
            "alias_quality": False,
            "enterprise_concept_quality": False,
            "reason": "Low lexical context overlap is a hard-negative candidate signal, not proof that a repeated surface term names different systems; shared context can still be boilerplate.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": result["coverage"], "collision_summary": result["collision_summary"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
