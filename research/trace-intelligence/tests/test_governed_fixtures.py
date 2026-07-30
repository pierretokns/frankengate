import json
import pathlib
import re
import unittest


FIXTURE_DIR = pathlib.Path(__file__).parents[1] / "fixtures" / "governed-v1"
EXPECTED_FIXTURES = {
    "authorization-epoch-advance.json",
    "authorized-result-no-state-delta.json",
    "cancellation-truncation.json",
    "deletion-lineage.json",
    "mixed-classification-scope-intersection.json",
    "observed-state-delta.json",
    "parallel-branch-join.json",
    "provider-fallback.json",
    "provider-retry.json",
    "redaction.json",
    "subagent-delegation.json",
    "tool-proposal-denied.json",
}
TRACE_ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def load_fixtures():
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURE_DIR.glob("*.json"))
    }


def event_index(fixture):
    return {event["event_id"]: event for event in fixture["events"]}


class GovernedFixtureTest(unittest.TestCase):
    def test_fixture_set_is_complete_and_deterministic(self):
        fixtures = load_fixtures()
        self.assertEqual(EXPECTED_FIXTURES, set(fixtures))
        trace_ids = [fixture["trace_id"] for fixture in fixtures.values()]
        self.assertEqual(len(trace_ids), len(set(trace_ids)))
        self.assertTrue(all(TRACE_ID_PATTERN.fullmatch(value) for value in trace_ids))

    def test_envelope_referential_integrity_and_loss_receipts(self):
        for name, fixture in load_fixtures().items():
            with self.subTest(fixture=name):
                self.assertEqual(
                    "canonical-trajectory-v1", fixture["schema_version"]
                )
                self.assertEqual(
                    "frankengate/governed-conformance",
                    fixture["source"]["dataset_id"],
                )
                self.assertEqual(
                    "governed-v1", fixture["source"]["dataset_revision"]
                )
                self.assertEqual(
                    "synthetic-governed-fixture-v1",
                    fixture["source"]["adapter"],
                )
                events = fixture["events"]
                by_id = event_index(fixture)
                self.assertEqual(len(events), len(by_id))
                self.assertEqual(list(range(len(events))), [e["sequence"] for e in events])
                self.assertEqual(
                    len(events), fixture["loss_receipt"]["source_event_count"]
                )
                self.assertEqual(
                    len(events), fixture["loss_receipt"]["canonical_event_count"]
                )
                self.assertEqual(
                    0, fixture["loss_receipt"]["silently_dropped_event_count"]
                )
                self.assertIsInstance(
                    fixture["loss_receipt"]["known_missing_fields"], list
                )
                self.assertTrue(fixture["loss_receipt"]["expected_invariants"])
                self.assertTrue(fixture["loss_receipt"]["expected_projection_losses"])

                sequence_by_id = {
                    event["event_id"]: event["sequence"] for event in events
                }
                for event in events:
                    self.assertIn("content", event)
                    self.assertIn(
                        event["observation_status"],
                        {"observed", "reconstructed", "inferred", "missing"},
                    )
                    for key, value in event.items():
                        if key.endswith("_event_id") and value is not None:
                            self.assertIn(value, by_id, key)
                            self.assertLess(sequence_by_id[value], event["sequence"], key)
                        elif key.endswith("_event_ids"):
                            self.assertIsInstance(value, list, key)
                            for reference in value:
                                self.assertIn(reference, by_id, key)
                                self.assertLess(
                                    sequence_by_id[reference], event["sequence"], key
                                )

                for evidence_id in fixture["outcome"]["evidence_event_ids"]:
                    self.assertIn(evidence_id, by_id)

                for invariant in fixture["loss_receipt"]["expected_invariants"]:
                    for key, value in invariant.items():
                        if key.endswith("_event_id"):
                            self.assertIn(value, by_id, key)
                        elif key.endswith("_event_ids"):
                            self.assertTrue(value, key)
                            self.assertTrue(all(item in by_id for item in value), key)

                for loss in fixture["loss_receipt"]["expected_projection_losses"]:
                    self.assertEqual("atif-v1.7", loss["target"])
                    self.assertIn(loss["disposition"], {"lost", "degraded"})
                    self.assertTrue(loss["feature"])
                    self.assertTrue(loss["reason"])

    def test_every_declared_invariant_has_an_executable_check(self):
        handlers = {
            "proposal_denied_not_executed": self.assert_proposal_denied,
            "authorized_execution": self.assert_authorized_execution,
            "result_without_observed_state_delta": self.assert_no_state_delta,
            "observed_state_delta_linked": self.assert_state_delta,
            "retry_within_user_attempt": self.assert_retry,
            "fallback_within_user_attempt": self.assert_fallback,
            "join_all_predecessors_observed": self.assert_join,
            "delegation_child_scoped": self.assert_delegation,
            "cancellation_is_terminal": self.assert_cancellation,
            "redaction_preserves_lineage": self.assert_redaction,
            "authorization_epoch_advance_invalidates": self.assert_epoch_advance,
            "deletion_invalidates_descendants": self.assert_deletion_lineage,
            "derived_scope_is_intersection": self.assert_scope_intersection,
        }
        seen = set()
        for name, fixture in load_fixtures().items():
            by_id = event_index(fixture)
            for invariant in fixture["loss_receipt"]["expected_invariants"]:
                invariant_type = invariant["type"]
                with self.subTest(fixture=name, invariant=invariant_type):
                    self.assertIn(invariant_type, handlers)
                    handlers[invariant_type](fixture, by_id, invariant)
                    seen.add(invariant_type)
        self.assertEqual(set(handlers), seen)

    def assert_proposal_denied(self, fixture, by_id, invariant):
        decision = by_id[invariant["decision_event_id"]]
        proposal = by_id[invariant["proposal_event_id"]]
        self.assertEqual("deny", decision["decision"])
        self.assertEqual("blocked", proposal["execution_status"])
        self.assertEqual(decision["event_id"], proposal["authorization_decision_event_id"])
        executions = [
            event
            for event in fixture["events"]
            if event["kind"] == "tool_execution"
            and event.get("proposal_event_id") == proposal["event_id"]
        ]
        self.assertEqual([], executions)

    def assert_authorized_execution(self, fixture, by_id, invariant):
        decision = by_id[invariant["decision_event_id"]]
        proposal = by_id[invariant["proposal_event_id"]]
        execution = by_id[invariant["execution_event_id"]]
        self.assertEqual("allow", decision["decision"])
        self.assertEqual(proposal["event_id"], execution["proposal_event_id"])
        self.assertEqual(decision["event_id"], execution["authorization_decision_event_id"])

    def assert_no_state_delta(self, fixture, by_id, invariant):
        result = by_id[invariant["result_event_id"]]
        execution = by_id[invariant["execution_event_id"]]
        self.assertEqual(execution["execution_id"], result["execution_id"])
        linked_deltas = [
            event
            for event in fixture["events"]
            if event["kind"] == "state_delta"
            and event.get("result_event_id") == result["event_id"]
        ]
        self.assertEqual([], linked_deltas)
        self.assertIn(
            "observed_state_delta", fixture["loss_receipt"]["known_missing_fields"]
        )

    def assert_state_delta(self, fixture, by_id, invariant):
        result = by_id[invariant["result_event_id"]]
        delta = by_id[invariant["state_delta_event_id"]]
        self.assertEqual(result["event_id"], delta["result_event_id"])
        self.assertNotEqual(delta["before_digest"], delta["after_digest"])

    def assert_retry(self, fixture, by_id, invariant):
        first = by_id[invariant["first_attempt_event_id"]]
        retry = by_id[invariant["retry_event_id"]]
        second = by_id[invariant["second_attempt_event_id"]]
        self.assertEqual(first["user_attempt_id"], second["user_attempt_id"])
        self.assertEqual(first["provider"], second["provider"])
        self.assertNotEqual(first["inference_attempt_id"], second["inference_attempt_id"])
        self.assertEqual(first["inference_attempt_id"], retry["from_attempt_id"])
        self.assertEqual(second["inference_attempt_id"], retry["to_attempt_id"])

    def assert_fallback(self, fixture, by_id, invariant):
        first = by_id[invariant["first_attempt_event_id"]]
        fallback = by_id[invariant["fallback_event_id"]]
        second = by_id[invariant["second_attempt_event_id"]]
        self.assertEqual(first["user_attempt_id"], second["user_attempt_id"])
        self.assertNotEqual(first["provider"], second["provider"])
        self.assertNotEqual(first["inference_attempt_id"], second["inference_attempt_id"])
        self.assertEqual(first["inference_attempt_id"], fallback["from_attempt_id"])
        self.assertEqual(second["inference_attempt_id"], fallback["to_attempt_id"])

    def assert_join(self, fixture, by_id, invariant):
        join = by_id[invariant["join_event_id"]]
        self.assertEqual(invariant["predecessor_event_ids"], join["predecessor_event_ids"])
        branches = {by_id[event_id]["branch_id"] for event_id in join["predecessor_event_ids"]}
        self.assertEqual({"branch-logs", "branch-deploy"}, branches)

    def assert_delegation(self, fixture, by_id, invariant):
        delegation = by_id[invariant["delegation_event_id"]]
        for event_id in invariant["child_event_ids"]:
            child = by_id[event_id]
            self.assertEqual(delegation["delegation_id"], child["delegation_id"])
            self.assertEqual(delegation["child_agent_id"], child["actor_id"])
        synthesis = by_id[invariant["synthesis_event_id"]]
        self.assertEqual(delegation["parent_agent_id"], synthesis["actor_id"])
        self.assertIn(invariant["child_event_ids"][-1], synthesis["evidence_event_ids"])

    def assert_cancellation(self, fixture, by_id, invariant):
        cancellation = by_id[invariant["cancellation_event_id"]]
        terminal = by_id[invariant["terminal_event_id"]]
        self.assertEqual("cancellation", cancellation["kind"])
        self.assertEqual("truncated", terminal["terminal_status"])
        self.assertEqual(len(fixture["events"]) - 1, terminal["sequence"])
        self.assertIn(
            "unobserved_stream_suffix", fixture["loss_receipt"]["known_missing_fields"]
        )

    def assert_redaction(self, fixture, by_id, invariant):
        redacted = by_id[invariant["redacted_event_id"]]
        receipt = by_id[invariant["receipt_event_id"]]
        self.assertIsNone(redacted["content"])
        self.assertEqual("redacted", redacted["redaction"]["status"])
        self.assertTrue(redacted["redaction"]["content_digest"].startswith("sha256:"))
        self.assertEqual(redacted["event_id"], receipt["redacted_event_id"])
        self.assertEqual(redacted["redaction"]["policy_id"], receipt["policy_id"])

    def assert_epoch_advance(self, fixture, by_id, invariant):
        prior = by_id[invariant["prior_decision_event_id"]]
        advance = by_id[invariant["advance_event_id"]]
        cache_check = by_id[invariant["cache_check_event_id"]]
        new = by_id[invariant["new_decision_event_id"]]
        self.assertEqual("allow", prior["decision"])
        self.assertEqual("deny", new["decision"])
        self.assertEqual(prior["authorization_epoch"], advance["prior_epoch"])
        self.assertEqual(new["authorization_epoch"], advance["new_epoch"])
        self.assertEqual("rejected", cache_check["cache_status"])
        self.assertLess(cache_check["cached_epoch"], cache_check["current_epoch"])
        self.assertEqual(prior["event_id"], new["supersedes_event_id"])

    def assert_deletion_lineage(self, fixture, by_id, invariant):
        source = by_id[invariant["source_event_id"]]
        derived = by_id[invariant["derived_event_id"]]
        tombstone = by_id[invariant["tombstone_event_id"]]
        invalidation = by_id[invariant["invalidation_event_id"]]
        self.assertIn(source["artifact_id"], derived["source_artifact_ids"])
        self.assertEqual(source["artifact_id"], tombstone["deleted_artifact_id"])
        self.assertEqual(
            derived["artifact_id"], invalidation["invalidated_artifact_id"]
        )
        self.assertEqual(tombstone["event_id"], invalidation["source_tombstone_event_id"])
        self.assertEqual("invalidated", invalidation["derivation_status"])

    def assert_scope_intersection(self, fixture, by_id, invariant):
        inputs = [by_id[event_id] for event_id in invariant["input_event_ids"]]
        derived = by_id[invariant["derived_event_id"]]
        expected_principals = set(inputs[0]["authorized_principals"])
        for event in inputs[1:]:
            expected_principals.intersection_update(event["authorized_principals"])
        self.assertEqual(expected_principals, set(derived["authorized_principals"]))
        rank = {
            value: index for index, value in enumerate(invariant["classification_order"])
        }
        expected_classification = max(
            (event["classification"] for event in inputs), key=rank.__getitem__
        )
        self.assertEqual(expected_classification, derived["classification"])


if __name__ == "__main__":
    unittest.main()
