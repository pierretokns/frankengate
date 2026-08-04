import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "native_tool_protocol_compliance.py"
)
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location(
    "native_tool_protocol_compliance",
    MODULE_PATH,
)
protocol = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = protocol
SPEC.loader.exec_module(protocol)


def native_call(name, arguments, call_id):
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, sort_keys=True),
        },
    }


class FakeDeterministicExecutor:
    """Unit-test executor that never parses or executes generated SQL."""

    def __init__(self, mode):
        self.mode = mode
        self.schema_calls = 0
        self.sql_calls = []

    def describe_schema(self):
        self.schema_calls += 1
        return {
            "status": "ok",
            "synthetic_schema": {"unit_test_relation": ["unit_id"]},
        }

    def execute_sql(self, *, sql, attempt_id, attempt_index):
        self.sql_calls.append((sql, attempt_id, attempt_index))
        if self.mode == "deny":
            return {
                "status": "synthetic_policy_denied",
                "attempt_id": attempt_id,
                "attempt_index": attempt_index,
            }
        return {
            "status": "ok",
            "attempt_id": attempt_id,
            "attempt_index": attempt_index,
            "synthetic_row_count": 1,
        }


class ToolAwareFakeAPI:
    request_model_id = "fake-native-tool-model"

    def __init__(self, expected_terminal_action):
        self.expected_terminal_action = expected_terminal_action
        self.calls = 0
        self.offered_tool_names = []

    @staticmethod
    def _latest_successful_attempt(messages):
        for message in reversed(messages):
            if message.get("role") != "tool":
                continue
            value = json.loads(message["content"])
            if value.get("status") == "ok" and value.get("attempt_id"):
                return value["attempt_id"]
        raise AssertionError("no successful attempt was observed")

    def complete(
        self,
        *,
        messages,
        tools,
        seed,
        max_tokens,
        timeout_seconds,
    ):
        self.calls += 1
        names = [
            item["function"]["name"]
            for item in tools
        ]
        self.offered_tool_names.append(names)
        if self.calls == 1:
            call = native_call("describe_schema", {}, "schema-1")
        elif self.calls == 2:
            call = native_call(
                "execute_sql",
                {"sql": "SELECT synthetic_step_one"},
                "sql-1",
            )
        elif self.calls == 3:
            call = native_call(
                "execute_sql",
                {"sql": "SELECT synthetic_step_two"},
                "sql-2",
            )
        elif self.calls == 4 and "execute_sql" in names:
            call = native_call(
                "execute_sql",
                {"sql": "SELECT synthetic_over_budget"},
                "sql-over-budget",
            )
        elif self.expected_terminal_action == "submit":
            call = native_call(
                "submit_sql",
                {
                    "attempt_id": self._latest_successful_attempt(messages)
                },
                "submit-1",
            )
        else:
            call = native_call(
                "abstain",
                {"reason_code": "tool_budget_exhausted"},
                "abstain-1",
            )
        response = {
            "system_fingerprint": "fake-runtime-v1",
            "usage": {
                "prompt_tokens": 7,
                "completion_tokens": 3,
            },
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [call],
                    },
                }
            ],
        }
        return response, 1.25


class TerminalFailureFakeAPI(ToolAwareFakeAPI):
    def complete(
        self,
        *,
        messages,
        tools,
        seed,
        max_tokens,
        timeout_seconds,
    ):
        if self.calls < 3:
            return super().complete(
                messages=messages,
                tools=tools,
                seed=seed,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
            )
        self.calls += 1
        self.offered_tool_names.append(
            [item["function"]["name"] for item in tools]
        )
        return {
            "system_fingerprint": "fake-runtime-v1",
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "plain text is not a terminal tool",
                    },
                }
            ],
        }, 1.25


class NativeToolProtocolComplianceTest(unittest.TestCase):
    def setUp(self):
        (
            self.manifest,
            self.limits,
            self.fixtures,
        ) = protocol.load_fixture()

    def test_fixture_is_content_free_paired_and_position_balanced(self):
        self.assertEqual(
            self.manifest["claim_scope"],
            "native_tool_protocol_compliance_only",
        )
        self.assertFalse(self.manifest["benchmark_content_used"])
        self.assertEqual(len(self.fixtures), 6)
        self.assertEqual(
            [item.expected_terminal_action for item in self.fixtures].count(
                "submit"
            ),
            3,
        )
        self.assertEqual(
            [item.expected_terminal_action for item in self.fixtures].count(
                "abstain"
            ),
            3,
        )
        for fixture in self.fixtures:
            self.assertEqual(
                set(fixture.variant_order),
                set(protocol.VARIANT_IDS),
            )
        for position in range(3):
            for variant in protocol.VARIANT_IDS:
                self.assertEqual(
                    sum(
                        item.variant_order[position] == variant
                        for item in self.fixtures
                    ),
                    2,
                )
        serialized = json.dumps(self.manifest).lower()
        self.assertNotIn("reference_sql", serialized)
        self.assertNotIn("gold_sql", serialized)
        self.assertNotIn("bird", serialized)
        self.assertNotIn("hidden_task", serialized)

    def test_three_variants_isolate_annotation_and_availability(self):
        baseline = protocol.tools_for_state(
            variant="always_all_tools",
            remaining_sql_attempts=0,
            remaining_schema_calls=0,
        )
        self.assertEqual(baseline, protocol.TOOLS)

        annotated = protocol.tools_for_state(
            variant="remaining_budget_annotations",
            remaining_sql_attempts=1,
            remaining_schema_calls=0,
        )
        self.assertEqual(
            [item["function"]["name"] for item in annotated],
            list(protocol.ALL_TOOL_NAMES),
        )
        self.assertTrue(
            all(
                "remaining_sql_attempts=1"
                in item["function"]["description"]
                for item in annotated
            )
        )
        self.assertEqual(
            [item["function"]["parameters"] for item in annotated],
            [item["function"]["parameters"] for item in protocol.TOOLS],
        )

        before_exhaustion = protocol.tools_for_state(
            variant="terminal_only_after_sql_budget",
            remaining_sql_attempts=1,
            remaining_schema_calls=0,
        )
        after_exhaustion = protocol.tools_for_state(
            variant="terminal_only_after_sql_budget",
            remaining_sql_attempts=0,
            remaining_schema_calls=0,
        )
        self.assertEqual(before_exhaustion, protocol.TOOLS)
        self.assertEqual(
            [item["function"]["name"] for item in after_exhaustion],
            ["submit_sql", "abstain"],
        )

    def test_external_raw_path_is_mandatory(self):
        with self.assertRaises(protocol.ProtocolExperimentError):
            protocol.require_external_raw_path(
                MODULE_PATH.parent / "raw-audit.jsonl"
            )
        with tempfile.TemporaryDirectory() as tmp:
            protocol.require_external_raw_path(
                pathlib.Path(tmp) / "raw-audit.jsonl"
            )

    def test_tool_loop_records_full_native_calls_externally(self):
        fixture = next(
            item
            for item in self.fixtures
            if item.expected_terminal_action == "submit"
        )
        api = ToolAwareFakeAPI("submit")
        executor = FakeDeterministicExecutor("success")
        with tempfile.TemporaryDirectory() as tmp:
            raw_path = pathlib.Path(tmp) / "episode.jsonl"
            receipt = protocol.run_episode(
                fixture=fixture,
                variant="terminal_only_after_sql_budget",
                limits=self.limits,
                api=api,
                executor=executor,
                raw_audit_path=raw_path,
            )
            records = [
                json.loads(line)
                for line in raw_path.read_text(encoding="utf-8").splitlines()
            ]
        native_calls = [
            item
            for item in records
            if item["event"] == "native_tool_call"
        ]
        requests = [
            item
            for item in records
            if item["event"] == "model_request"
        ]
        self.assertEqual(receipt.terminal_action, "submit")
        self.assertTrue(receipt.expected_terminal_match)
        self.assertEqual(receipt.sql_attempts, 2)
        self.assertEqual(receipt.over_budget_sql_calls, 0)
        self.assertEqual(receipt.unavailable_tool_calls, 0)
        self.assertEqual(len(native_calls), 4)
        self.assertTrue(
            all("call" in item and "parsed_arguments" in item for item in native_calls)
        )
        self.assertEqual(
            native_calls[1]["parsed_arguments"]["sql"],
            "SELECT synthetic_step_one",
        )
        self.assertEqual(
            [
                item["function"]["name"]
                for item in requests[-1]["tools"]
            ],
            ["submit_sql", "abstain"],
        )
        self.assertEqual(
            receipt.raw_audit_sha256,
            protocol.hashlib.sha256(
                "\n".join(
                    json.dumps(
                        item,
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                    for item in records
                ).encode("utf-8")
                + b"\n"
            ).hexdigest(),
        )

    def test_always_all_tools_exposes_over_budget_call_to_runner(self):
        fixture = next(
            item
            for item in self.fixtures
            if item.expected_terminal_action == "submit"
        )
        api = ToolAwareFakeAPI("submit")
        with tempfile.TemporaryDirectory() as tmp:
            receipt = protocol.run_episode(
                fixture=fixture,
                variant="always_all_tools",
                limits=self.limits,
                api=api,
                executor=FakeDeterministicExecutor("success"),
                raw_audit_path=pathlib.Path(tmp) / "baseline.jsonl",
            )
        self.assertEqual(receipt.terminal_action, "submit")
        self.assertEqual(receipt.over_budget_sql_calls, 1)
        self.assertEqual(receipt.unavailable_tool_calls, 0)
        self.assertIn("execute_sql", api.offered_tool_names[-2])

    def test_terminal_failure_is_explicit(self):
        fixture = next(
            item
            for item in self.fixtures
            if item.expected_terminal_action == "submit"
        )
        with tempfile.TemporaryDirectory() as tmp:
            receipt = protocol.run_episode(
                fixture=fixture,
                variant="terminal_only_after_sql_budget",
                limits=self.limits,
                api=TerminalFailureFakeAPI("submit"),
                executor=FakeDeterministicExecutor("success"),
                raw_audit_path=pathlib.Path(tmp) / "failure.jsonl",
            )
        self.assertEqual(receipt.terminal_action, "none")
        self.assertEqual(receipt.terminal_outcome, "terminal_failure")
        self.assertEqual(
            receipt.terminal_failure_code,
            "text_without_terminal_tool",
        )

    def test_full_fake_schedule_aggregates_submit_abstain_failure_rates(self):
        receipts = []
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = pathlib.Path(tmp)
            for fixture in self.fixtures:
                for variant in fixture.variant_order:
                    api = ToolAwareFakeAPI(
                        fixture.expected_terminal_action
                    )
                    executor = FakeDeterministicExecutor(
                        fixture.executor_mode
                    )
                    receipts.append(
                        protocol.run_episode(
                            fixture=fixture,
                            variant=variant,
                            limits=self.limits,
                            api=api,
                            executor=executor,
                            raw_audit_path=raw_dir
                            / f"{fixture.fixture_id}-{variant}.jsonl",
                        )
                    )
            aggregate = protocol.aggregate_receipts(
                receipts=receipts,
                fixture_manifest=self.manifest,
                fixture_sha256=protocol.sha256_file(
                    protocol.FIXTURE_PATH
                ),
                request_model_id="fake-native-tool-model",
            )
        self.assertEqual(
            aggregate["claim_scope"],
            "native_tool_protocol_compliance_only",
        )
        self.assertFalse(aggregate["benchmark_content_used"])
        self.assertEqual(len(aggregate["episode_receipts"]), 18)
        for variant in protocol.VARIANT_IDS:
            result = aggregate["variant_results"][variant]
            self.assertEqual(result["episodes"], 6)
            self.assertEqual(result["terminal_submit_count"], 3)
            self.assertEqual(result["terminal_submit_rate"], 0.5)
            self.assertEqual(result["terminal_abstain_count"], 3)
            self.assertEqual(result["terminal_abstain_rate"], 0.5)
            self.assertEqual(result["terminal_failure_count"], 0)
            self.assertEqual(result["terminal_failure_rate"], 0.0)
            self.assertEqual(
                result["expected_terminal_match_rate"],
                1.0,
            )
        self.assertEqual(
            aggregate["variant_results"][
                "terminal_only_after_sql_budget"
            ]["over_budget_sql_calls"],
            0,
        )
        self.assertEqual(
            aggregate["variant_results"]["always_all_tools"][
                "over_budget_sql_calls"
            ],
            6,
        )
        self.assertEqual(
            aggregate["variant_results"][
                "remaining_budget_annotations"
            ]["over_budget_sql_calls"],
            6,
        )


if __name__ == "__main__":
    unittest.main()
