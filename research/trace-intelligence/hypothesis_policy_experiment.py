#!/usr/bin/env python3
"""Run two deterministic proposal policies plus a no-proposal control."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import dream_release_pipeline_v2 as dreams


def _evidence(evidence_id: str, content: str) -> dreams.Evidence:
    envelope = dreams.AuthorityEnvelope(
        tenant_id="tenant-a", owner_subject_id="alice", audience="private",
        team_id=None, classification=2, purposes=("support", "debug"),
        authorization_epoch=7, policy_revision="policy-v1",
    )
    return dreams.Evidence(
        evidence_id=evidence_id, content=content,
        observed_at=dreams.instant("2026-01-01T00:00:00Z"),
        source_ref=f"trace://{evidence_id}", envelope=envelope,
    )


def _run(policy: str, *, propose: bool) -> dict[str, object]:
    pipeline = dreams.DreamReleasePipeline()
    pipeline.add_evidence(_evidence("e1", "tool failed then recovered"))
    pipeline.add_evidence(_evidence("e2", "same recovery observed again"))
    job = pipeline.start_dream(
        generator_id=f"policy-{policy}", generator_revision="policy-v1",
        cutoff=dreams.instant("2026-02-01T00:00:00Z"),
    )
    proposal_ids: list[str] = []
    if propose:
        citations = ("e1",) if policy == "conservative" else ("e1", "e2")
        proposal = pipeline.submit_proposal(
            job_id=job.job_id,
            content=("Review this recovery pattern" if policy == "conservative" else "Prefer the recovered tool path"),
            citation_ids=citations,
            generator_rationale="deterministic policy rationale",
        )
        packet = pipeline.verifier_packet(proposal.proposal_id)
        verification = pipeline.record_verification(
            proposal_id=proposal.proposal_id, verifier_id=f"verifier-{policy}",
            verifier_revision="verifier-v1", verdict="verified",
            verified_at=dreams.instant("2026-02-02T00:00:00Z"),
        )
        assert packet.packet_digest == verification.packet_digest
        proposal_ids.append(proposal.proposal_id)
        pipeline.release(proposal_ids=tuple(proposal_ids), released_at=dreams.instant("2026-02-03T00:00:00Z"))
    visible_before_delete = len(pipeline.visible_proposals(
        at=dreams.instant("2026-02-03T01:00:00Z"),
        authority=dreams.QueryAuthority("tenant-a", "alice", (), 2, "support", 7),
    ))
    if propose:
        pipeline.delete_evidence("e1", deleted_at=dreams.instant("2026-02-04T00:00:00Z"))
    visible_after_delete = len(pipeline.visible_proposals(
        at=dreams.instant("2026-02-04T01:00:00Z"),
        authority=dreams.QueryAuthority("tenant-a", "alice", (), 2, "support", 7),
    ))
    return {"policy": policy, "proposals": len(proposal_ids), "visible_before_delete": visible_before_delete, "visible_after_delete": visible_after_delete}


def main() -> int:
    rows = [_run("conservative", propose=True), _run("pooled", propose=True), _run("none", propose=False)]
    result = {
        "schema_version": "fg-hypothesis-policy-experiment-v1",
        "policies": rows,
        "proposal_policies_run": 2,
        "no_proposal_control_run": True,
        "held_out_outcome": False,
        "causal_claim": False,
        "raw_content_emitted": False,
    }
    result["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
