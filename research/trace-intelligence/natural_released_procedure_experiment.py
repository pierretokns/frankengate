#!/usr/bin/env python3
"""Exercise a real query-independent release on natural public traces.

The parent natural-trace factorial correctly left Dream/procedure arms gated:
there was no independently released derived item.  This experiment closes
that *mechanics* gap without claiming utility.  It creates one deterministic,
content-minimized procedure proposal per anonymous source/project from only
pre-cutoff evidence, verifies it with a distinct verifier identity, releases
it before the first eligible query, and independently checks lineage and
authority visibility.  The proposal itself is a digest-backed procedure
record, not a substitute for the original artifact; exact task utility is
therefore reported separately and never inferred from release success.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import dream_release_pipeline_v2 as pipeline
import natural_trace_memory_factorial as natural


SCHEMA_VERSION = "frankengate-natural-released-procedure-v1"
IDENTITY_SEED = b"frankengate-natural-released-procedure-public-v1"


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def opaque(namespace: str, value: str) -> str:
    return namespace + "-" + hashlib.sha256((namespace + "\0" + value).encode()).hexdigest()[:24]


def envelope(owner: str) -> pipeline.AuthorityEnvelope:
    return pipeline.AuthorityEnvelope(
        tenant_id="public-study-tenant",
        owner_subject_id=owner,
        audience="private",
        team_id=None,
        classification=0,
        purposes=("trace-analysis",),
        authorization_epoch=1,
        policy_revision="natural-release-v1",
    )


def independent_verify(
    proposal: pipeline.Proposal,
    packet: pipeline.VerificationPacket,
    *,
    cutoff,
    release_at,
) -> dict[str, Any]:
    """Verify lineage without using the pipeline's verification decision."""
    cited = {row.evidence_id: row for row in packet.evidence}
    checks = {
        "packet_matches_proposal": packet.proposal_id == proposal.proposal_id
        and packet.content == proposal.content,
        "citations_nonempty": bool(proposal.citation_ids),
        "all_citations_present": set(proposal.citation_ids) == set(cited),
        "all_evidence_pre_cutoff": all(row.observed_at <= cutoff for row in cited.values()),
        "release_after_verification_boundary": release_at >= cutoff,
        "content_digests_match": all(
            row.content_digest == hashlib.sha256(
                pipeline.stable_json(row.content).encode()
            ).hexdigest()
            for row in cited.values()
        ),
        "distinct_verifier_required": True,
    }
    return {"all_passed": all(checks.values()), "checks": checks}


def load_queries(config_path: Path, sources: Sequence[natural.SourceSpec]) -> tuple[list[Any], list[dict[str, Any]]]:
    config = natural.load_protocol_config(config_path)
    key = hashlib.sha256(IDENTITY_SEED).digest()
    queries: list[Any] = []
    receipts: list[dict[str, Any]] = []
    for source in sources:
        interactions, parents, bounds, receipt, _ = natural._load_source(source, key)
        observations, _ = natural._construct_observations(
            interactions,
            parents_by_session=parents,
            session_bounds=bounds,
            identity_key=key,
        )
        selected, _ = natural._construct_queries(
            interactions,
            observations,
            parents_by_session=parents,
            session_bounds=bounds,
        )
        queries.extend(selected)
        receipts.append(receipt)
    if not queries:
        raise RuntimeError("no natural queries were admitted")
    return queries, receipts


def run(queries: Sequence[Any], receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_project: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for query in queries:
        by_project[(query.source_label, query.project_private)].append(query)

    project_rows: list[dict[str, Any]] = []
    verifier_rows: list[dict[str, Any]] = []
    total_baseline_exact = 0
    total_procedure_exact = 0
    total_visible = 0
    total_citation_target = 0
    for project_index, ((source, project), project_queries) in enumerate(sorted(by_project.items())):
        ordered = sorted(project_queries, key=lambda item: item.query_at)
        first = ordered[0]
        release_at = first.query_at - timedelta(microseconds=1)
        cutoff = release_at - timedelta(microseconds=1)
        candidates = [item for item in first.candidates if item.observed_at <= cutoff]
        if not candidates:
            continue
        candidates = candidates[: min(3, len(candidates))]
        owner = opaque("owner", project)
        authority = envelope(owner)
        store = pipeline.DreamReleasePipeline()
        evidence_ids: list[str] = []
        for index, observation in enumerate(candidates):
            evidence_id = opaque("evidence", f"{source}\0{project}\0{index}\0{observation.content_sha256}")
            evidence_ids.append(evidence_id)
            store.add_evidence(
                pipeline.Evidence(
                    evidence_id=evidence_id,
                    content=observation.content,
                    observed_at=observation.observed_at,
                    source_ref=opaque("source", observation.observation_private),
                    envelope=authority,
                )
            )
        job = store.start_dream(
            generator_id="deterministic-procedure-generator",
            generator_revision="natural-procedure-digest-v1",
            cutoff=cutoff,
        )
        procedure_content = (
            "Frankengate recovery procedure v1\n"
            "Use only the latest authorized pre-query context artifact; verify "
            "its evidence lineage before applying it.\n"
            f"evidence_count={len(evidence_ids)}\n"
            f"evidence_set_digest={digest(sorted(evidence_ids))}"
        )
        proposal = store.submit_proposal(
            job_id=job.job_id,
            content=procedure_content,
            citation_ids=tuple(evidence_ids),
            generator_rationale="Fixed query-independent procedure derived only from pre-cutoff evidence.",
        )
        packet = store.verifier_packet(proposal.proposal_id)
        independent = independent_verify(
            proposal,
            packet,
            cutoff=cutoff,
            release_at=release_at,
        )
        verification = store.record_verification(
            proposal_id=proposal.proposal_id,
            verifier_id="independent-procedure-verifier",
            verifier_revision="natural-procedure-verifier-v1",
            verdict="verified" if independent["all_passed"] else "contradicted",
            verified_at=release_at,
        )
        snapshot = store.release(proposal_ids=(proposal.proposal_id,), released_at=release_at)
        visible_queries = 0
        citation_target_queries = 0
        exact_queries = 0
        baseline_exact = 0
        for query in project_queries:
            baseline_outcome, _ = natural._decide(query, ("latest_snapshot",))
            baseline_exact += int(baseline_outcome == "exact")
            visible = store.visible_proposals(
                at=query.query_at,
                authority=pipeline.QueryAuthority(
                    tenant_id="public-study-tenant",
                    subject_id=owner,
                    teams=(),
                    classification_ceiling=0,
                    purpose="trace-analysis",
                    authorization_epoch=1,
                ),
            )
            visible_queries += bool(visible)
            citation_target = any(
                item.content_digest == query.target_content_sha256
                for item in packet.evidence
            )
            citation_target_queries += citation_target
            exact_queries += int(any(
                hashlib.sha256(item.content.encode()).hexdigest()
                == query.target_content_sha256
                for item in visible
            ))
        total_baseline_exact += baseline_exact
        total_procedure_exact += exact_queries
        total_visible += visible_queries
        total_citation_target += citation_target_queries
        project_rows.append({
            "source": source,
            "query_count": len(project_queries),
            "expert_release_before_first_query": snapshot.released_at < first.query_at,
            "proposal_status": store.proposal_status(proposal.proposal_id),
            "cited_evidence_count": len(evidence_ids),
            "visible_query_count": visible_queries,
            "citation_target_query_count": citation_target_queries,
            "procedure_exact_query_count": exact_queries,
            "baseline_exact_query_count": baseline_exact,
            "release_id_digest": digest(snapshot.release_id),
            "proposal_id_digest": digest(proposal.proposal_id),
        })
        verifier_rows.append({
            "source": source,
            "checks_passed": independent["all_passed"],
            "checks": independent["checks"],
            "verification_verdict": verification.verdict,
            "release_lineage_count": len(snapshot.proposals[0].source_lineage),
            "release_before_first_query": snapshot.released_at < first.query_at,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "study": "natural_query_independent_released_procedure_mechanics",
        "input_receipts": list(receipts),
        "protocol": {
            "source_scope": "same anonymous source/project only",
            "proposal_generation": "deterministic digest-backed procedure from pre-cutoff evidence",
            "cutoff": "strictly before first eligible query per project",
            "verifier": "distinct identity and independent lineage checks",
            "release": "atomic governed pipeline release",
        },
        "aggregate": {
            "admitted_queries": len(queries),
            "projects_with_release": len(project_rows),
            "projects": len(by_project),
            "baseline_exact_queries": total_baseline_exact,
            "procedure_exact_queries": total_procedure_exact,
            "visible_procedure_query_count": total_visible,
            "citation_target_query_count": total_citation_target,
            "verifier_passed_projects": sum(row["checks_passed"] for row in verifier_rows),
        },
        "project_rows": project_rows,
        "verifier_rows": verifier_rows,
        "claim_boundary": {
            "release_mechanics_confirmed": bool(project_rows) and all(row["checks_passed"] for row in verifier_rows),
            "natural_released_procedure_evaluated": bool(project_rows),
            "procedure_quality_confirmed": False,
            "causal_memory_or_skill_utility_confirmed": False,
            "enterprise_transfer_confirmed": False,
            "reason": "The released artifact is intentionally digest-backed and query-independent; exact target matching is a diagnostic only, not a semantic utility oracle.",
        },
        "content_policy": {
            "raw_content_emitted": False,
            "paths_emitted": False,
            "native_identifiers_emitted": False,
            "per_item_content_emitted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol-config", type=Path, required=True)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    sources = [natural._parse_source(value) for value in args.source]
    queries, receipts = load_queries(args.protocol_config, sources)
    result = run(queries, receipts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    aggregate = result["aggregate"]
    args.summary.write_text(
        "# Natural released-procedure mechanics\n\n"
        f"Built and released {aggregate['projects_with_release']} query-independent "
        f"procedures across {aggregate['admitted_queries']} admitted natural queries. "
        f"Independent release verification passed for {aggregate['verifier_passed_projects']} "
        "projects. This confirms governed release mechanics only; it does not confirm "
        "procedure quality, memory utility, or enterprise transfer.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "aggregate": aggregate}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
