#!/usr/bin/env python3
"""Faithful Graphiti/LangMem component experiment helpers.

The executable adapter in ``faithful_memory_components_run.py`` uses the real
upstream libraries.  This module keeps cohort selection, scoring, aggregation,
and durable-output validation dependency-free so those experiment contracts
remain testable without installing the isolated research environment.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Any, Mapping, Sequence


class FaithfulComponentError(ValueError):
    """Raised when an experiment or durable-output invariant is violated."""


@dataclass(frozen=True)
class SelectedNaturalCase:
    """One deterministic natural query selected for faithful component work."""

    source_label: str
    changed: bool
    query: Any
    projected_revision_count: int
    projected_bytes: int


@dataclass(frozen=True)
class IdentifierScore:
    reference_identifiers: int
    extracted_identifiers: int
    matched_identifiers: int
    recall: float | None
    precision: float | None


@dataclass(frozen=True)
class ComponentCaseResult:
    """Content-free measurements emitted by a single natural case."""

    source_label: str
    changed: bool
    baseline_exact: bool
    graphiti_retrieval_exact: bool
    graphiti_temporal_edges: int
    graphiti_invalidated_edges: int
    graphiti_identifier_recall: float | None
    langmem_identifier_recall: float | None
    langmem_memory_count: int
    langmem_updated_existing: bool
    combined_retrieval_exact: bool
    graphiti_status: str = "executed"
    langmem_status: str = "executed"
    combined_status: str = "executed"
    graphiti_node_count: int = 0
    graphiti_edge_count: int = 0


def sha256_text(value: str) -> str:
    if not isinstance(value, str):
        raise FaithfulComponentError("text must be a string")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_natural_contrast_queries(
    queries: Sequence[Any],
    *,
    max_revisions: int = 2,
) -> list[SelectedNaturalCase]:
    """Select the smallest changed/unchanged query in each source stratum.

    Only the newest ``max_revisions`` eligible pre-query observations are
    projected to the component experiment.  Selection depends on source label,
    change status, byte count, revision count, and the already-private query
    identity; it never inspects the post-query content.
    """

    if max_revisions < 1:
        raise FaithfulComponentError("max_revisions must be positive")
    by_stratum: dict[tuple[str, bool], SelectedNaturalCase] = {}
    for query in queries:
        candidates = tuple(getattr(query, "candidates", ()))
        if not candidates:
            continue
        projected = candidates[:max_revisions]
        latest_digest = sha256_text(projected[0].content)
        changed = latest_digest != query.target_content_sha256
        row = SelectedNaturalCase(
            source_label=str(query.source_label),
            changed=changed,
            query=query,
            projected_revision_count=len(projected),
            projected_bytes=sum(
                len(item.content.encode("utf-8")) for item in projected
            ),
        )
        stratum = (row.source_label, row.changed)
        incumbent = by_stratum.get(stratum)
        ordering = (
            row.projected_bytes,
            row.projected_revision_count,
            str(query.query_private),
        )
        incumbent_ordering = (
            incumbent.projected_bytes,
            incumbent.projected_revision_count,
            str(incumbent.query.query_private),
        ) if incumbent is not None else None
        if incumbent is None or ordering < incumbent_ordering:
            by_stratum[stratum] = row
    return sorted(
        by_stratum.values(),
        key=lambda row: (row.source_label, row.changed),
    )


_IDENTIFIER_PATTERNS = (
    re.compile(r"(?<!\w)/(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+"),
    re.compile(r"\b[A-Za-z][A-Za-z0-9-]*\.[A-Za-z0-9_.-]+\b"),
    re.compile(r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+\b"),
    re.compile(r"\b[a-z]+(?:[A-Z][A-Za-z0-9]*)+\b"),
    re.compile(r"\b[A-Z][A-Z0-9]{1,9}\b"),
)


def corporate_identifiers(text: str) -> set[str]:
    """Extract exact-term candidates whose loss matters in corporate traces."""

    if not isinstance(text, str):
        raise FaithfulComponentError("identifier input must be text")
    occupied: list[tuple[int, int]] = []
    values: set[str] = set()
    for pattern in _IDENTIFIER_PATTERNS:
        for match in pattern.finditer(text):
            if any(
                match.start() < end and match.end() > start
                for start, end in occupied
            ):
                continue
            token = match.group(0).rstrip(".,:;)")
            if len(token) < 3:
                continue
            values.add(token.casefold())
            occupied.append((match.start(), match.end()))
    return values


def score_identifier_preservation(
    reference: str,
    extracted: str,
) -> IdentifierScore:
    expected = corporate_identifiers(reference)
    observed = corporate_identifiers(extracted)
    matched = expected & observed
    return IdentifierScore(
        reference_identifiers=len(expected),
        extracted_identifiers=len(observed),
        matched_identifiers=len(matched),
        recall=(
            round(len(matched) / len(expected), 12)
            if expected
            else None
        ),
        precision=(
            round(len(matched) / len(observed), 12)
            if observed
            else None
        ),
    )


def _mean(values: Sequence[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return round(sum(present) / len(present), 12) if present else None


def aggregate_component_results(
    rows: Sequence[ComponentCaseResult],
) -> dict[str, Any]:
    """Aggregate only evidence that the faithful component run measured."""

    baseline = sum(row.baseline_exact for row in rows)
    graphiti = sum(row.graphiti_retrieval_exact for row in rows)
    combined = sum(row.combined_retrieval_exact for row in rows)
    graphiti_executed = sum(
        row.graphiti_status == "executed" for row in rows
    )
    langmem_executed = sum(
        row.langmem_status == "executed" for row in rows
    )
    combined_executed = sum(
        row.combined_status == "executed" for row in rows
    )
    return {
        "cases": len(rows),
        "changed_cases": sum(row.changed for row in rows),
        "graphiti_executed_cases": graphiti_executed,
        "langmem_executed_cases": langmem_executed,
        "combined_executed_cases": combined_executed,
        "baseline_exact": baseline,
        "graphiti_retrieval_exact": graphiti,
        "graphiti_minus_baseline_exact": (
            graphiti - baseline
            if graphiti_executed == len(rows)
            else None
        ),
        "combined_retrieval_exact": combined,
        "combined_minus_baseline_exact": (
            combined - baseline
            if combined_executed == len(rows)
            else None
        ),
        "graphiti_temporal_edges": sum(
            row.graphiti_temporal_edges for row in rows
        ),
        "graphiti_invalidated_edges": sum(
            row.graphiti_invalidated_edges for row in rows
        ),
        "graphiti_node_count": sum(
            row.graphiti_node_count for row in rows
        ),
        "graphiti_edge_count": sum(
            row.graphiti_edge_count for row in rows
        ),
        "graphiti_mean_identifier_recall": _mean(
            [row.graphiti_identifier_recall for row in rows]
        ),
        "langmem_mean_identifier_recall": _mean(
            [row.langmem_identifier_recall for row in rows]
        ),
        "langmem_memory_count": sum(
            row.langmem_memory_count for row in rows
        ),
        "langmem_updated_existing_cases": sum(
            row.langmem_updated_existing for row in rows
        ),
        "claim_boundary": (
            "component_mechanics_and_natural_prequery_retrieval_only"
        ),
    }


def assert_durable_result(result: Mapping[str, Any]) -> None:
    """Reject a result that claims to emit source content or identifiers."""

    policy = result.get("content_policy")
    required_false = (
        "raw_content_emitted",
        "artifact_paths_emitted",
        "native_identifiers_emitted",
        "per_case_identifiers_emitted",
    )
    if not isinstance(policy, Mapping) or any(
        policy.get(field) is not False for field in required_false
    ):
        raise FaithfulComponentError("durable output policy is violated")


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def result_digest(result: Mapping[str, Any]) -> str:
    body = dict(result)
    body.pop("result_sha256", None)
    return hashlib.sha256(_stable_json(body).encode("utf-8")).hexdigest()


def verify_result(result: Mapping[str, Any]) -> bool:
    digest = result.get("result_sha256")
    return (
        isinstance(digest, str)
        and len(digest) == 64
        and hmac.compare_digest(digest, result_digest(result))
    )
