import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import trace_signal_diagnosis_eval_chain as chain  # noqa: E402


RECEIPT_KEY = b"test-receipt-key-that-is-at-least-32-bytes"


class TraceSignalDiagnosisEvalChainTest(unittest.TestCase):
    def make_trace(self, trace_ref, events):
        return chain.TraceEvidence(
            trace_ref=trace_ref,
            events=tuple(
                chain.TraceEvent(
                    event_id=f"{trace_ref}-event-{index}",
                    order=index,
                    **event,
                )
                for index, event in enumerate(events)
            ),
            source_records=len(events),
            malformed_records=0,
            credential_transformations=0,
            credential_counts={},
            source_sha256="0" * 64,
        )

    def test_ingestion_preserves_pii_but_excludes_credentials(self):
        records = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "Please help alice@example.com debug the deploy",
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call-1",
                            "name": "Bash",
                            "input": {
                                "command": (
                                    "curl -H 'Authorization: Bearer "
                                    "abcdefghijklmnopqrstuv' "
                                    "https://internal.example/alice@example.com"
                                ),
                                "api_key": "sk_test_abcdefghijklmnopqrstuvwxyz",
                            },
                        }
                    ],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call-1",
                            "is_error": True,
                            "content": "alice@example.com received HTTP 403",
                        }
                    ],
                },
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory) / "trace.jsonl"
            source.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            trace = chain.ingest_wisp_file(
                source,
                corpus_root=pathlib.Path(directory),
                receipt_hmac_key=RECEIPT_KEY,
                scope_ref="test-private-scope",
            )

        serialized_events = json.dumps(
            [event.content for event in trace.events],
            sort_keys=True,
        )
        self.assertIn("alice@example.com", serialized_events)
        self.assertNotIn("abcdefghijklmnopqrstuv", serialized_events)
        self.assertNotIn("sk_test_abcdefghijklmnopqrstuvwxyz", serialized_events)
        self.assertIn("[CREDENTIAL:", serialized_events)
        self.assertEqual(2, trace.credential_transformations)
        self.assertEqual(3, trace.source_records)

    def test_cheap_signals_select_behavior_not_trace_length(self):
        problematic = self.make_trace(
            "problematic",
            [
                {
                    "kind": "conversation.user",
                    "role": "user",
                    "content": "Why did deploy fail?",
                },
                {
                    "kind": "conversation.user",
                    "role": "user",
                    "content": "  why did DEPLOY fail? ",
                },
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"command":"deploy"}',
                    "tool_name": "Bash",
                    "call_id": "c1",
                },
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"permission denied"',
                    "call_id": "c1",
                    "is_error": True,
                },
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"command":"deploy"}',
                    "tool_name": "Bash",
                    "call_id": "c2",
                },
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"permission denied"',
                    "call_id": "c2",
                    "is_error": True,
                },
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"command":"deploy"}',
                    "tool_name": "Bash",
                    "call_id": "c3",
                },
            ],
        )
        healthy = self.make_trace(
            "healthy",
            [
                {
                    "kind": "conversation.text",
                    "role": "assistant",
                    "content": f"distinct response {index}",
                }
                for index in range(30)
            ],
        )

        report = chain.cheap_signals(problematic)
        selected = chain.select_for_review(
            [healthy, problematic],
            budget=1,
        )

        self.assertEqual(
            {
                "dangling_tool_proposal": 1,
                "explicit_tool_error": 2,
                "repeated_failure": 1,
                "repeated_tool_action": 1,
                "rephrasing": 1,
            },
            report.detector_counts,
        )
        self.assertGreater(report.score, 0)
        self.assertEqual(("problematic",), tuple(item.trace_ref for item in selected))

    def test_selection_does_not_pad_budget_with_signal_free_traces(self):
        healthy = self.make_trace(
            "healthy-only",
            [
                {
                    "kind": "conversation.text",
                    "role": "assistant",
                    "content": "ordinary completion",
                }
            ],
        )

        selected = chain.select_for_review([healthy], budget=10)

        self.assertEqual((), selected)

    def test_rephrasing_includes_list_form_user_text(self):
        trace = self.make_trace(
            "list-user-text",
            [
                {
                    "kind": "conversation.text",
                    "role": "user",
                    "content": "Can you inspect the deployment?",
                },
                {
                    "kind": "conversation.text",
                    "role": "user",
                    "content": " can YOU inspect the deployment? ",
                },
            ],
        )

        report = chain.cheap_signals(trace)

        self.assertEqual(1, report.detector_counts["rephrasing"])

    def test_diagnosis_localizes_earliest_repeated_failure_as_hypothesis(self):
        trace = self.make_trace(
            "repeated-failure",
            [
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"command":"deploy"}',
                    "tool_name": "Bash",
                    "call_id": "c1",
                },
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"permission denied"',
                    "call_id": "c1",
                    "is_error": True,
                },
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"command":"deploy"}',
                    "tool_name": "Bash",
                    "call_id": "c2",
                },
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"permission denied"',
                    "call_id": "c2",
                    "is_error": True,
                },
            ],
        )

        diagnosis = chain.diagnose_trace(trace, chain.cheap_signals(trace))

        self.assertEqual("hypothesis", diagnosis.epistemic_status)
        self.assertEqual("repeated_tool_failure", diagnosis.failure_taxonomy)
        self.assertEqual("repeated-failure-event-1", diagnosis.decisive_event_id)
        self.assertEqual(
            ("repeated-failure-event-1", "repeated-failure-event-3"),
            diagnosis.evidence_event_ids,
        )
        self.assertIn("permission_or_authority", diagnosis.alternatives)
        self.assertNotIn("root cause", diagnosis.hypothesis.casefold())

    def test_diagnosis_prioritizes_correlation_invariant_violation(self):
        trace = self.make_trace(
            "orphan-result",
            [
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"failed without proposal"',
                    "call_id": "missing-call",
                    "is_error": True,
                },
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": "{}",
                    "tool_name": "Read",
                    "call_id": "later",
                },
            ],
        )

        diagnosis = chain.diagnose_trace(trace, chain.cheap_signals(trace))

        self.assertEqual("orphan_tool_result", diagnosis.failure_taxonomy)
        self.assertEqual("orphan-result-event-0", diagnosis.decisive_event_id)
        self.assertEqual(("orphan-result-event-0",), diagnosis.evidence_event_ids)

    def test_diagnosis_keeps_single_explicit_error_contestable(self):
        trace = self.make_trace(
            "single-error",
            [
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"path":"/internal/alice"}',
                    "tool_name": "Read",
                    "call_id": "c1",
                },
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"file missing"',
                    "call_id": "c1",
                    "is_error": True,
                },
            ],
        )

        diagnosis = chain.diagnose_trace(trace, chain.cheap_signals(trace))

        self.assertEqual("hypothesis", diagnosis.epistemic_status)
        self.assertEqual("explicit_tool_failure", diagnosis.failure_taxonomy)
        self.assertEqual(("single-error-event-1",), diagnosis.evidence_event_ids)
        self.assertGreaterEqual(len(diagnosis.alternatives), 4)

    def test_single_explicit_failure_promotes_a_replay_regression_assertion(self):
        trace = self.make_trace(
            "promotable-error",
            [
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"path":"/internal/alice"}',
                    "tool_name": "Read",
                    "call_id": "c1",
                },
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"file missing"',
                    "call_id": "c1",
                    "is_error": True,
                },
            ],
        )
        diagnosis = chain.diagnose_trace(trace, chain.cheap_signals(trace))

        bundle = chain.promote_eval_bundle(trace, diagnosis)

        self.assertEqual(1, len(bundle.stored_trace_assertions))
        self.assertEqual(1, len(bundle.changed_system_assertions))
        self.assertEqual(
            "fail",
            chain.evaluate_assertions(
                trace,
                bundle.changed_system_assertions,
            )[0].status,
        )

    def test_eval_promotion_separates_stored_audit_from_changed_system_replay(self):
        observed = self.make_trace(
            "observed",
            [
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"command":"deploy"}',
                    "tool_name": "Bash",
                    "call_id": "c1",
                },
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"permission denied"',
                    "call_id": "c1",
                    "is_error": True,
                },
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"command":"deploy"}',
                    "tool_name": "Bash",
                    "call_id": "c2",
                },
                {
                    "kind": "tool.result.error",
                    "role": "user",
                    "content": '"permission denied"',
                    "call_id": "c2",
                    "is_error": True,
                },
            ],
        )
        changed = self.make_trace(
            "changed",
            [
                {
                    "kind": "tool.proposed",
                    "role": "assistant",
                    "content": '{"command":"deploy"}',
                    "tool_name": "Bash",
                    "call_id": "n1",
                },
                {
                    "kind": "tool.result.success",
                    "role": "user",
                    "content": '"deployed"',
                    "call_id": "n1",
                },
            ],
        )
        diagnosis = chain.diagnose_trace(observed, chain.cheap_signals(observed))

        bundle = chain.promote_eval_bundle(observed, diagnosis)
        stored = chain.evaluate_assertions(
            observed,
            bundle.stored_trace_assertions,
        )
        unchanged_replay = chain.evaluate_assertions(
            observed,
            bundle.changed_system_assertions,
        )
        changed_replay = chain.evaluate_assertions(
            changed,
            bundle.changed_system_assertions,
        )

        self.assertEqual(("pass",), tuple(item.status for item in stored))
        self.assertEqual(("fail",), tuple(item.status for item in unchanged_replay))
        self.assertEqual(("pass",), tuple(item.status for item in changed_replay))
        self.assertEqual(
            "stored_trace_audit",
            bundle.stored_trace_assertions[0].evaluation_mode,
        )
        self.assertEqual(
            "changed_system_replay",
            bundle.changed_system_assertions[0].evaluation_mode,
        )
        self.assertNotIn(
            "permission denied",
            json.dumps(bundle, default=lambda item: item.__dict__),
        )

    def test_end_to_end_result_is_content_free_and_labels_mutation_replay_as_proxy(self):
        failing_records = [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "secret-native-call-id",
                            "name": "Bash",
                            "input": {"command": "deploy alice@example.com"},
                        }
                    ],
                },
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "secret-native-call-id",
                            "is_error": True,
                            "content": "sentinel private permission failure",
                        }
                    ],
                },
            },
        ]
        healthy_records = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "another private prompt",
                },
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "private-failure.jsonl").write_text(
                "".join(
                    json.dumps(record) + "\n"
                    for record in failing_records
                ),
                encoding="utf-8",
            )
            (root / "private-healthy.jsonl").write_text(
                "".join(
                    json.dumps(record) + "\n"
                    for record in healthy_records
                ),
                encoding="utf-8",
            )

            result = chain.run_wisp_experiment(
                root,
                receipt_hmac_key=RECEIPT_KEY,
                scope_ref="private-test-scope",
                review_budget=10,
                dataset_id="synthetic-private-test",
                dataset_revision="fixture-v1",
                run_date="2026-07-30",
            )

        serialized = json.dumps(result, sort_keys=True)
        for forbidden in (
            "alice@example.com",
            "sentinel private permission failure",
            "secret-native-call-id",
            "private-failure.jsonl",
            "private-healthy.jsonl",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertTrue(result["content_free"])
        self.assertEqual(1, result["selection"]["selected_traces"])
        self.assertEqual(
            1,
            result["eval_promotion"]["changed_system_assertions"],
        )
        self.assertEqual(
            0,
            result["replay"]["actual_changed_system_runs"],
        )
        self.assertEqual(
            "mutation_proxy_not_changed_system_replay",
            result["replay"]["proxy_kind"],
        )
        summary = chain.render_markdown(result)
        self.assertIn("not changed-system replay", summary.casefold())
        self.assertIn(
            "actual changed-system executions: **0**",
            summary.casefold(),
        )


if __name__ == "__main__":
    unittest.main()
