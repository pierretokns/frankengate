import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "dream_release_pipeline_v2.py"
SPEC = importlib.util.spec_from_file_location("dream_release_pipeline_v2", MODULE_PATH)
dreams = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = dreams
SPEC.loader.exec_module(dreams)


def private_envelope(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "owner_subject_id": "alice",
        "audience": "private",
        "team_id": None,
        "classification": 2,
        "purposes": ("support", "debug"),
        "authorization_epoch": 7,
        "policy_revision": "policy-v1",
    }
    values.update(overrides)
    return dreams.AuthorityEnvelope(**values)


def evidence(
    evidence_id,
    content,
    observed_at,
    *,
    source_ref=None,
    envelope=None,
):
    return dreams.Evidence(
        evidence_id=evidence_id,
        content=content,
        observed_at=dreams.instant(observed_at),
        source_ref=source_ref or f"trace://{evidence_id}",
        envelope=envelope or private_envelope(),
    )


class DreamReleasePipelineV2Test(unittest.TestCase):
    def _verified_proposal(self, pipeline, job, evidence_id, content):
        proposal = pipeline.submit_proposal(
            job_id=job.job_id,
            content=content,
            citation_ids=(evidence_id,),
            generator_rationale="never sent to verifier",
        )
        pipeline.record_verification(
            proposal_id=proposal.proposal_id,
            verifier_id="verifier-b",
            verifier_revision="verifier-v1",
            verdict="verified",
            verified_at=dreams.instant("2026-02-02T00:00:00Z"),
        )
        return proposal

    def test_dream_input_is_query_independent_and_cutoff_safe(self):
        pipeline = dreams.DreamReleasePipeline()
        pipeline.add_evidence(
            evidence("before", "known before cutoff", "2026-01-01T00:00:00Z")
        )
        pipeline.add_evidence(
            evidence("future", "future target answer", "2026-03-01T00:00:00Z")
        )

        dream_input = pipeline.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )

        self.assertEqual(("before",), tuple(row.evidence_id for row in dream_input.evidence))
        self.assertFalse(hasattr(dream_input, "target_query"))
        self.assertNotIn("future target answer", dreams.stable_json(dream_input))

    def test_proposal_citations_must_exist_in_the_frozen_pre_cutoff_input(self):
        pipeline = dreams.DreamReleasePipeline()
        pipeline.add_evidence(
            evidence("before", "known before cutoff", "2026-01-01T00:00:00Z")
        )
        job = pipeline.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )
        pipeline.add_evidence(
            evidence("late-added", "not in frozen input", "2026-01-15T00:00:00Z")
        )

        with self.assertRaises(dreams.DreamProtocolError):
            pipeline.submit_proposal(
                job_id=job.job_id,
                content="unsupported",
                citation_ids=("missing",),
                generator_rationale="hidden chain of thought",
            )
        with self.assertRaises(dreams.DreamProtocolError):
            pipeline.submit_proposal(
                job_id=job.job_id,
                content="late leak",
                citation_ids=("late-added",),
                generator_rationale="hidden chain of thought",
            )

        proposal = pipeline.submit_proposal(
            job_id=job.job_id,
            content="supported summary",
            citation_ids=("before",),
            generator_rationale="hidden chain of thought",
        )
        self.assertEqual(("before",), proposal.citation_ids)

    def test_independent_verifier_packet_excludes_generator_rationale_and_identity(self):
        pipeline = dreams.DreamReleasePipeline()
        pipeline.add_evidence(
            evidence("e1", "observable fact", "2026-01-01T00:00:00Z")
        )
        job = pipeline.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )
        proposal = pipeline.submit_proposal(
            job_id=job.job_id,
            content="candidate fact",
            citation_ids=("e1",),
            generator_rationale="private generator reasoning",
        )

        packet = pipeline.verifier_packet(proposal.proposal_id)

        packet_json = dreams.stable_json(packet)
        self.assertNotIn("private generator reasoning", packet_json)
        self.assertNotIn("generator-a", packet_json)
        self.assertFalse(hasattr(packet, "generator_rationale"))
        self.assertEqual("candidate fact", packet.content)
        self.assertEqual(("e1",), tuple(row.evidence_id for row in packet.evidence))

        with self.assertRaises(dreams.DreamProtocolError):
            pipeline.record_verification(
                proposal_id=proposal.proposal_id,
                verifier_id="generator-a",
                verifier_revision="verifier-v1",
                verdict="verified",
                verified_at=dreams.instant("2026-02-02T00:00:00Z"),
            )

    def test_nonverified_verdicts_are_quarantined_and_cannot_be_released(self):
        for verdict in ("unverified", "contradicted", "insufficient"):
            with self.subTest(verdict=verdict):
                pipeline = dreams.DreamReleasePipeline()
                pipeline.add_evidence(
                    evidence("e1", "observable fact", "2026-01-01T00:00:00Z")
                )
                job = pipeline.start_dream(
                    generator_id="generator-a",
                    generator_revision="extractor-v2",
                    cutoff=dreams.instant("2026-02-01T00:00:00Z"),
                )
                proposal = pipeline.submit_proposal(
                    job_id=job.job_id,
                    content="candidate fact",
                    citation_ids=("e1",),
                    generator_rationale="not disclosed",
                )
                pipeline.record_verification(
                    proposal_id=proposal.proposal_id,
                    verifier_id="verifier-b",
                    verifier_revision="verifier-v1",
                    verdict=verdict,
                    verified_at=dreams.instant("2026-02-02T00:00:00Z"),
                )

                self.assertEqual("quarantined", pipeline.proposal_status(proposal.proposal_id))
                self.assertEqual(
                    verdict,
                    pipeline.quarantine_record(proposal.proposal_id).reason,
                )
                with self.assertRaises(dreams.DreamProtocolError):
                    pipeline.release(
                        proposal_ids=(proposal.proposal_id,),
                        released_at=dreams.instant("2026-02-03T00:00:00Z"),
                    )

    def test_quarantine_is_terminal_and_cannot_be_overwritten_by_a_later_verdict(self):
        pipeline = dreams.DreamReleasePipeline()
        pipeline.add_evidence(
            evidence("e1", "observable fact", "2026-01-01T00:00:00Z")
        )
        job = pipeline.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )
        proposal = pipeline.submit_proposal(
            job_id=job.job_id,
            content="candidate fact",
            citation_ids=("e1",),
            generator_rationale="not disclosed",
        )
        pipeline.record_verification(
            proposal_id=proposal.proposal_id,
            verifier_id="verifier-b",
            verifier_revision="verifier-v1",
            verdict="insufficient",
            verified_at=dreams.instant("2026-02-02T00:00:00Z"),
        )

        with self.assertRaises(dreams.DreamProtocolError):
            pipeline.record_verification(
                proposal_id=proposal.proposal_id,
                verifier_id="verifier-c",
                verifier_revision="verifier-v2",
                verdict="verified",
                verified_at=dreams.instant("2026-02-03T00:00:00Z"),
            )
        self.assertEqual("quarantined", pipeline.proposal_status(proposal.proposal_id))

        with self.assertRaises(dreams.DreamProtocolError):
            pipeline.submit_proposal(
                job_id=job.job_id,
                content="candidate fact",
                citation_ids=("e1",),
                generator_rationale="different private rationale",
            )
        self.assertEqual("quarantined", pipeline.proposal_status(proposal.proposal_id))

    def test_proposal_authority_is_the_fail_closed_intersection_of_citations(self):
        pipeline = dreams.DreamReleasePipeline()
        pipeline.add_evidence(
            evidence(
                "e1",
                "one",
                "2026-01-01T00:00:00Z",
                envelope=private_envelope(
                    classification=2,
                    purposes=("support", "debug"),
                    authorization_epoch=6,
                ),
            )
        )
        pipeline.add_evidence(
            evidence(
                "e2",
                "two",
                "2026-01-02T00:00:00Z",
                envelope=private_envelope(
                    classification=4,
                    purposes=("support", "audit"),
                    authorization_epoch=7,
                ),
            )
        )
        job = pipeline.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )

        proposal = pipeline.submit_proposal(
            job_id=job.job_id,
            content="combined",
            citation_ids=("e1", "e2"),
            generator_rationale="not disclosed",
        )

        self.assertEqual(4, proposal.envelope.classification)
        self.assertEqual(("support",), proposal.envelope.purposes)
        self.assertEqual(7, proposal.envelope.authorization_epoch)
        self.assertEqual("private", proposal.envelope.audience)

        other = dreams.DreamReleasePipeline()
        other.add_evidence(
            evidence(
                "e1",
                "one",
                "2026-01-01T00:00:00Z",
                envelope=private_envelope(purposes=("support",)),
            )
        )
        other.add_evidence(
            evidence(
                "e2",
                "two",
                "2026-01-02T00:00:00Z",
                envelope=private_envelope(purposes=("audit",)),
            )
        )
        other_job = other.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )
        with self.assertRaises(dreams.DreamProtocolError):
            other.submit_proposal(
                job_id=other_job.job_id,
                content="no common authority",
                citation_ids=("e1", "e2"),
                generator_rationale="not disclosed",
            )

    def test_release_is_atomic_copy_on_write_and_preserves_source_lineage(self):
        pipeline = dreams.DreamReleasePipeline()
        for number in range(1, 4):
            pipeline.add_evidence(
                evidence(
                    f"e{number}",
                    f"fact {number}",
                    f"2026-01-0{number}T00:00:00Z",
                )
            )
        job = pipeline.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )
        first = self._verified_proposal(pipeline, job, "e1", "candidate one")
        second = self._verified_proposal(pipeline, job, "e2", "candidate two")
        third = self._verified_proposal(pipeline, job, "e3", "candidate three")

        release_one = pipeline.release(
            proposal_ids=(first.proposal_id,),
            released_at=dreams.instant("2026-02-03T00:00:00Z"),
        )
        self.assertIsNone(release_one.parent_release_id)
        self.assertEqual((first.proposal_id,), tuple(row.proposal_id for row in release_one.proposals))
        lineage = release_one.proposals[0].source_lineage
        self.assertEqual(("e1",), tuple(row.evidence_id for row in lineage))
        self.assertEqual(("trace://e1",), tuple(row.source_ref for row in lineage))
        self.assertEqual(job.job_id, release_one.proposals[0].dream_job_id)
        self.assertEqual("extractor-v2", release_one.proposals[0].generator_revision)
        self.assertEqual("verifier-v1", release_one.proposals[0].verifier_revision)

        pipeline.delete_evidence(
            "e3", deleted_at=dreams.instant("2026-02-04T00:00:00Z")
        )
        before_failed_batch = pipeline.release_history()
        with self.assertRaises(dreams.DreamProtocolError):
            pipeline.release(
                proposal_ids=(second.proposal_id, third.proposal_id),
                released_at=dreams.instant("2026-02-05T00:00:00Z"),
            )
        self.assertEqual(before_failed_batch, pipeline.release_history())
        self.assertEqual((first.proposal_id,), tuple(row.proposal_id for row in release_one.proposals))

        release_two = pipeline.release(
            proposal_ids=(second.proposal_id,),
            released_at=dreams.instant("2026-02-05T00:00:00Z"),
        )
        self.assertEqual(release_one.release_id, release_two.parent_release_id)
        self.assertEqual(
            (first.proposal_id, second.proposal_id),
            tuple(row.proposal_id for row in release_two.proposals),
        )
        self.assertEqual((first.proposal_id,), tuple(row.proposal_id for row in release_one.proposals))

    def test_only_released_authorized_proposals_are_visible_after_release_time(self):
        pipeline = dreams.DreamReleasePipeline()
        pipeline.add_evidence(
            evidence("e1", "observable fact", "2026-01-01T00:00:00Z")
        )
        job = pipeline.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )
        proposal = self._verified_proposal(pipeline, job, "e1", "candidate one")
        authority = dreams.QueryAuthority(
            tenant_id="tenant-a",
            subject_id="alice",
            teams=(),
            classification_ceiling=2,
            purpose="support",
            authorization_epoch=7,
        )

        self.assertEqual(
            (),
            pipeline.visible_proposals(
                at=dreams.instant("2026-02-05T00:00:00Z"),
                authority=authority,
            ),
        )
        pipeline.release(
            proposal_ids=(proposal.proposal_id,),
            released_at=dreams.instant("2026-02-10T00:00:00Z"),
        )
        self.assertEqual(
            (),
            pipeline.visible_proposals(
                at=dreams.instant("2026-02-09T23:59:59Z"),
                authority=authority,
            ),
        )
        visible = pipeline.visible_proposals(
            at=dreams.instant("2026-02-10T00:00:00Z"),
            authority=authority,
        )
        self.assertEqual((proposal.proposal_id,), tuple(row.proposal_id for row in visible))
        self.assertTrue(all(isinstance(row, dreams.ReleasedProposal) for row in visible))

        wrong_owner = dreams.QueryAuthority(
            tenant_id="tenant-a",
            subject_id="mallory",
            teams=(),
            classification_ceiling=9,
            purpose="support",
            authorization_epoch=7,
        )
        self.assertEqual(
            (),
            pipeline.visible_proposals(
                at=dreams.instant("2026-02-11T00:00:00Z"),
                authority=wrong_owner,
            ),
        )

    def test_deleted_evidence_invalidates_a_released_proposal_from_deletion_time(self):
        pipeline = dreams.DreamReleasePipeline()
        pipeline.add_evidence(
            evidence("e1", "observable fact", "2026-01-01T00:00:00Z")
        )
        job = pipeline.start_dream(
            generator_id="generator-a",
            generator_revision="extractor-v2",
            cutoff=dreams.instant("2026-02-01T00:00:00Z"),
        )
        proposal = self._verified_proposal(pipeline, job, "e1", "candidate one")
        pipeline.release(
            proposal_ids=(proposal.proposal_id,),
            released_at=dreams.instant("2026-02-03T00:00:00Z"),
        )
        pipeline.delete_evidence(
            "e1", deleted_at=dreams.instant("2026-02-05T00:00:00Z")
        )
        authority = dreams.QueryAuthority(
            tenant_id="tenant-a",
            subject_id="alice",
            teams=(),
            classification_ceiling=2,
            purpose="support",
            authorization_epoch=7,
        )

        before_deletion = pipeline.visible_proposals(
            at=dreams.instant("2026-02-04T00:00:00Z"),
            authority=authority,
        )
        after_deletion = pipeline.visible_proposals(
            at=dreams.instant("2026-02-05T00:00:00Z"),
            authority=authority,
        )

        self.assertEqual((proposal.proposal_id,), tuple(row.proposal_id for row in before_deletion))
        self.assertEqual((), after_deletion)


if __name__ == "__main__":
    unittest.main()
