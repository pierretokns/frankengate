import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

try:
    import sqlglot  # noqa: F401
except ModuleNotFoundError as exc:  # optional NL2SQL factorial dependency
    raise unittest.SkipTest("sqlglot is required for Defog SQL factorial") from exc


MODULE_PATH = pathlib.Path(__file__).parents[1] / "defog_sql_factorial.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("defog_sql_factorial", MODULE_PATH)
factorial = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = factorial
SPEC.loader.exec_module(factorial)


class FakeAPI:
    request_model_id = "default_model"
    max_tokens = 1024

    def __init__(self):
        self.calls = 0

    def complete(
        self,
        *,
        messages,
        seed,
        tools=None,
        max_tokens=None,
        timeout_seconds=None,
    ):
        self.calls += 1
        base = {
            "system_fingerprint": "test-runtime",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        if self.calls == 1:
            message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "schema-1",
                        "type": "function",
                        "function": {
                            "name": "describe_schema",
                            "arguments": "{}",
                        },
                    }
                ],
            }
        elif self.calls == 2:
            message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "sql-1",
                        "type": "function",
                        "function": {
                            "name": "execute_sql",
                            "arguments": json.dumps(
                                {"sql": "SELECT COUNT(*) AS n FROM orders"}
                            ),
                        },
                    }
                ],
            }
        elif self.calls == 3:
            tool_result = json.loads(messages[-1]["content"])
            message = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "submit-1",
                        "type": "function",
                        "function": {
                            "name": "submit_sql",
                            "arguments": json.dumps(
                                {"attempt_id": tool_result["attempt_id"]}
                            ),
                        },
                    }
                ],
            }
        else:
            message = {"role": "assistant", "content": "There are two."}
        return {
            **base,
            "choices": [{"finish_reason": "stop", "message": message}],
        }, 2.5


class NoSubmissionAPI(FakeAPI):
    def complete(
        self,
        *,
        messages,
        seed,
        tools=None,
        max_tokens=None,
        timeout_seconds=None,
    ):
        if self.calls < 2:
            return super().complete(
                messages=messages,
                seed=seed,
                tools=tools,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
            )
        self.calls += 1
        return {
            "system_fingerprint": "test-runtime",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "There are two.",
                    },
                }
            ],
        }, 2.5


class TerminalBudgetAPI(FakeAPI):
    """Keeps retrying SQL until the observation declares terminal state."""

    def __init__(self):
        super().__init__()
        self.offered_tool_names = []
        self.latest_attempt_id = None

    def complete(
        self,
        *,
        messages,
        seed,
        tools=None,
        max_tokens=None,
        timeout_seconds=None,
    ):
        self.calls += 1
        names = [
            item["function"]["name"]
            for item in (tools or factorial.TOOLS)
        ]
        self.offered_tool_names.append(names)
        observation = {}
        for message in reversed(messages):
            if message.get("role") != "tool":
                continue
            observation = json.loads(message["content"])
            if observation.get("attempt_id"):
                self.latest_attempt_id = observation["attempt_id"]
            break
        terminal_required = (
            observation.get("protocol_state", {}).get(
                "required_terminal_action"
            )
            is True
            and messages[-1]
            == {
                "role": "user",
                "content": factorial.TERMINAL_STATE_CONTROL_MESSAGE,
            }
        )
        if self.calls == 1:
            call = {
                "id": "schema-1",
                "type": "function",
                "function": {
                    "name": "describe_schema",
                    "arguments": "{}",
                },
            }
        elif not terminal_required:
            call = {
                "id": f"sql-{self.calls}",
                "type": "function",
                "function": {
                    "name": "execute_sql",
                    "arguments": json.dumps(
                        {"sql": f"SELECT {self.calls} AS n"}
                    ),
                },
            }
        else:
            call = {
                "id": "submit-1",
                "type": "function",
                "function": {
                    "name": "submit_sql",
                    "arguments": json.dumps(
                        {"attempt_id": self.latest_attempt_id}
                    ),
                },
            }
        return {
            "system_fingerprint": "test-runtime",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "tool_calls": [call],
                    },
                }
            ],
        }, 2.5


class AbstainAPI(FakeAPI):
    def complete(
        self,
        *,
        messages,
        seed,
        tools=None,
        max_tokens=None,
        timeout_seconds=None,
    ):
        self.calls += 1
        return {
            "system_fingerprint": "test-runtime",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "abstain-1",
                                "type": "function",
                                "function": {
                                    "name": "abstain",
                                    "arguments": json.dumps(
                                        {
                                            "reason_code": (
                                                "insufficient_schema"
                                            )
                                        }
                                    ),
                                },
                            }
                        ],
                    },
                }
            ],
        }, 2.5


class DroppedToolAPI(FakeAPI):
    def complete(
        self,
        *,
        messages,
        seed,
        tools=None,
        max_tokens=None,
        timeout_seconds=None,
    ):
        self.calls += 1
        return {
            "system_fingerprint": "test-runtime",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {"role": "assistant", "content": ""},
                }
            ],
        }, 2.5


class FakeExecutor:
    def __init__(self):
        self.candidate_executions = 0

    def catalog(self):
        return {"public.orders": frozenset({"id", "amount"})}

    def execute_candidate(self, sql):
        self.candidate_executions += 1
        return types.SimpleNamespace(order_sensitive=False), factorial.QueryResult(
            columns=("n",),
            rows=((2,),),
            elapsed_ms=1.0,
            result_bytes=10,
        )

    def execute_gold_alternatives(self, sql):
        statement = types.SimpleNamespace(find_all=lambda kind: ())
        return [
            (
                statement,
                factorial.QueryResult(
                    columns=("n",),
                    rows=((2,),),
                    elapsed_ms=1.0,
                    result_bytes=10,
                ),
            )
        ]


class FakeHTTPResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "done",
                        }
                    }
                ]
            }
        ).encode("utf-8")


def content_free_run_receipt(arm):
    return factorial.RunReceipt(
        task_id_sha256="a" * 64,
        arm=arm,
        seed=1,
        semantic_correct=False,
        strict_answer_shape_correct=False,
        authority_valid=True,
        policy_accepted=None,
        execution_completed=False,
        unauthorized_observation=False,
        outcome="no_terminal_submission",
        terminal_action="none",
        submitted_attempt_id=None,
        abstain_reason_code=None,
        protocol_failure_code=None,
        policy_error_code=None,
        candidate_sql_sha256=None,
        final_answer_sha256=None,
        attempt_receipts=(),
        attempt_receipt_chain_sha256="b" * 64,
        authority_binding_sha256="c" * 64,
        authority_epoch_ref_sha256="d" * 64,
        authority_snapshot_sha256="e" * 64,
        model_calls=1,
        tool_calls=0,
        schema_calls=0,
        sql_attempts=0,
        successful_sql_attempts=0,
        prompt_tokens=1,
        completion_tokens=1,
        elapsed_ms=1.0,
        system_fingerprint="runtime",
        raw_audit_sha256="f" * 64,
    )


class DefogSQLFactorialTest(unittest.TestCase):
    def test_task_seed_is_paired_across_arms(self):
        task_id = "task-1"
        first = factorial._task_seed(task_id, 20260730)
        second = factorial._task_seed(task_id, 20260730)
        self.assertEqual(first, second)
        self.assertNotEqual(
            first, factorial._task_seed("task-2", 20260730)
        )

    def test_runner_uses_the_preregistered_arm_order(self):
        arms = [
            "no_skill",
            "unrelated_formatting_placebo",
            "expert_schema_navigation_seed",
        ]
        frozen = [
            "expert_schema_navigation_seed",
            "no_skill",
            "unrelated_formatting_placebo",
        ]
        fold = {
            "arm_order": {
                "mechanics_smoke": {"task-1": frozen}
            }
        }
        self.assertEqual(
            frozen,
            factorial._frozen_arm_order(
                fold=fold,
                task_id="task-1",
                arms=arms,
            ),
        )
        self.assertEqual(
            ["no_skill", "unrelated_formatting_placebo"],
            factorial._frozen_arm_order(
                fold=fold,
                task_id="task-1",
                arms=[
                    "no_skill",
                    "unrelated_formatting_placebo",
                ],
            )
        )

    def test_chat_api_sends_only_the_pinned_server_request_alias(self):
        api = factorial.ChatAPI(
            endpoint="http://127.0.0.1:18080",
            request_model_id="default_model",
            timeout_seconds=1,
            max_tokens=32,
        )
        with patch.object(
            factorial,
            "urlopen",
            return_value=FakeHTTPResponse(),
        ) as opener:
            api.complete(
                messages=[{"role": "user", "content": "test"}],
                tools=[
                    tool
                    for tool in factorial.TOOLS
                    if tool["function"]["name"]
                    in factorial.TERMINAL_TOOL_NAMES
                ],
                seed=7,
            )
        request = opener.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual("default_model", payload["model"])
        self.assertNotIn("mlx-community", request.data.decode("utf-8"))
        self.assertNotIn("tool_choice", payload)
        self.assertEqual(0, payload["top_k"])
        self.assertEqual(0, payload["min_p"])
        self.assertEqual(32, payload["max_completion_tokens"])
        self.assertEqual(
            ["submit_sql", "abstain"],
            [tool["function"]["name"] for tool in payload["tools"]],
        )

    def test_model_result_preview_is_row_and_byte_bounded(self):
        result = factorial.QueryResult(
            columns=("payload",),
            rows=tuple(("x" * 250,) for _ in range(20)),
            elapsed_ms=1.0,
            result_bytes=5000,
        )
        rendered = factorial._model_result(
            result,
            preview_rows=10,
            preview_bytes=700,
        )
        payload = json.loads(rendered)
        self.assertLessEqual(len(rendered.encode("utf-8")), 700)
        self.assertLess(len(payload["rows"]), 10)
        self.assertTrue(payload["preview_truncated"])

    def test_raw_audit_directory_must_be_outside_repository(self):
        with self.assertRaisesRegex(
            factorial.FactorialError,
            "outside the research repository",
        ):
            factorial._require_external_raw_audit_dir(
                MODULE_PATH.parent / "raw"
            )
        with tempfile.TemporaryDirectory() as temporary:
            factorial._require_external_raw_audit_dir(
                pathlib.Path(temporary)
            )

    def test_one_task_smoke_records_selected_and_executed_counts(self):
        arms = [
            "no_skill",
            "unrelated_formatting_placebo",
            "expert_schema_navigation_seed",
        ]
        tasks = {
            f"task-{index}": factorial.RuntimeTask(
                task_id=f"task-{index}",
                database="fixture",
                query_category="basic",
                question="external raw question",
                instructions="",
                gold_sql="SELECT 1",
            )
            for index in range(4)
        }
        calls = []
        validations = []

        class Resolver:
            def __init__(self, **kwargs):
                pass

            def resolve(self, task_id):
                return tasks[task_id]

        class API:
            def __init__(self, **kwargs):
                self.request_model_id = kwargs["request_model_id"]

        class Executor:
            def __init__(self, **kwargs):
                self.authority = kwargs["authority"]

        class AuthorityStore:
            snapshot_sha256 = "e" * 64

            def validate(self, **kwargs):
                validations.append(kwargs)
                return factorial.AuthorityReceipt(
                    binding_sha256="c" * 64,
                    epoch_ref_sha256="d" * 64,
                    authority_snapshot_sha256=self.snapshot_sha256,
                )

        def fake_run_agent(**kwargs):
            calls.append(kwargs)
            return content_free_run_receipt(kwargs["arm"])

        with tempfile.TemporaryDirectory() as temporary:
            base = pathlib.Path(temporary)
            model = base / "model.json"
            model.write_text(
                json.dumps(
                    {
                        "model_id": "immutable/repository",
                        "request_model_id": "default_model",
                        "revision": "1" * 40,
                        "snapshot_identity_sha256": "2" * 64,
                        "runtime": {"name": "test"},
                    }
                ),
                encoding="utf-8",
            )
            cohort = base / "cohort.json"
            dataset = base / "dataset.json"
            authority = base / "authority.json"
            for path in (cohort, dataset, authority):
                path.write_text("{}", encoding="utf-8")
            frozen_order = [
                "expert_schema_navigation_seed",
                "no_skill",
                "unrelated_formatting_placebo",
            ]
            design = base / "design.json"
            design.write_text(
                json.dumps(
                    {
                        "seed": 20260730,
                        "model_manifest_sha256": (
                            factorial.sha256_file(model)
                        ),
                        "authority_manifest_sha256": (
                            factorial.sha256_file(authority)
                        ),
                        "prompt_contract": {
                            "base_system_prompt_sha256": (
                                factorial.sha256_text(
                                    factorial.BASE_SYSTEM_PROMPT
                                )
                            ),
                            "arm_artifacts": {
                                arm: {
                                    "artifact_sha256": (
                                        factorial.sha256_text(artifact)
                                    )
                                }
                                for arm, artifact in (
                                    factorial.ARM_PROMPTS.items()
                                )
                            },
                        },
                        "tool_contract": {
                            "tools_sha256": (
                                factorial.hashlib.sha256(
                                    factorial.canonical_json_bytes(
                                        factorial.TOOLS
                                    )
                                ).hexdigest()
                            )
                        },
                        "limits": {
                            "max_model_turns": 6,
                            "max_sql_attempts": 3,
                            "max_generated_tokens_per_call": 1024,
                        },
                        "folds": [
                            {
                                "fold_id": "fold-0",
                                "mechanics_smoke_task_ids": list(tasks),
                                "visible_selection_database_family": (
                                    "fixture"
                                ),
                                "arm_order": {
                                    "mechanics_smoke": {
                                        task_id: frozen_order
                                        for task_id in tasks
                                    }
                                },
                            }
                        ],
                        "arm_contracts": {
                            arm: {"classification": "test"}
                            for arm in arms
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(factorial, "PinnedTaskResolver", Resolver), patch.object(
                factorial, "ChatAPI", API
            ), patch.object(
                factorial,
                "GovernedPostgresExecutor",
                Executor,
            ), patch.object(
                factorial.StaticAuthorityEpochStore,
                "from_path",
                return_value=AuthorityStore(),
            ), patch.object(
                factorial,
                "run_agent",
                side_effect=fake_run_agent,
            ):
                result = factorial.run_factorial(
                    source_root=base,
                    cohort_manifest_path=cohort,
                    dataset_manifest_path=dataset,
                    design_manifest_path=design,
                    model_manifest_path=model,
                    authority_manifest_path=authority,
                    fold_id="fold-0",
                    arms=arms,
                    dsn_template="dbname={database}",
                    endpoint="http://127.0.0.1:18080",
                    raw_audit_dir=base / "raw",
                    output_path=base / "aggregate.json",
                    max_model_turns=6,
                    max_sql_attempts=3,
                    max_tokens=1024,
                    request_timeout_seconds=10,
                    task_limit=1,
                )
        self.assertEqual("mechanics_smoke", result["classification"])
        self.assertEqual("one_task_smoke", result["run_scope"])
        self.assertEqual(4, result["selected_task_count"])
        self.assertEqual(1, result["executed_task_count"])
        self.assertEqual(3, result["trajectory_count"])
        self.assertEqual(
            frozen_order,
            [call["arm"] for call in calls],
        )
        self.assertEqual(3, len(validations))
        self.assertTrue(
            all(
                item["authorization_epoch_ref"]
                == factorial.AUTHORIZATION_EPOCH_REF
                for item in validations
            )
        )
        self.assertEqual(
            "default_model",
            result["model"]["request_model_id"],
        )
        self.assertEqual(
            "immutable/repository",
            result["model"]["model_id"],
        )

    def test_arm_claims_are_explicit(self):
        self.assertIn(
            'id="none"',
            factorial.ARM_PROMPTS["no_skill"],
        )
        self.assertIn(
            "SQL presentation checklist",
            factorial.ARM_PROMPTS["unrelated_formatting_placebo"],
        )
        self.assertIn(
            "Inspect relevant tables and columns",
            factorial.ARM_PROMPTS["expert_schema_navigation_seed"],
        )
        self.assertNotIn(
            "trace-mined",
            factorial._system_prompt("expert_schema_navigation_seed").lower(),
        )

    def test_agent_uses_native_tools_and_emits_content_free_receipt(self):
        task = factorial.RuntimeTask(
            task_id="task-1",
            database="fixture",
            query_category="basic",
            question="How many orders exist?",
            instructions="",
            gold_sql="SELECT COUNT(*) FROM orders",
        )
        executor = FakeExecutor()
        with tempfile.TemporaryDirectory() as temporary:
            raw_path = pathlib.Path(temporary) / "raw.jsonl"
            with patch.object(
                factorial,
                "results_equal",
                return_value=True,
            ) as equality:
                receipt = factorial.run_agent(
                    task=task,
                    arm="no_skill",
                    seed=7,
                    api=FakeAPI(),
                    executor=executor,
                    limits=factorial.AgentLimits(),
                    raw_audit_path=raw_path,
                )
            raw = raw_path.read_text(encoding="utf-8")
        self.assertTrue(receipt.semantic_correct)
        self.assertEqual("semantic_correct", receipt.outcome)
        self.assertEqual("submit_sql", receipt.terminal_action)
        self.assertEqual(1, executor.candidate_executions)
        equality.assert_called_once()
        self.assertEqual(3, receipt.model_calls)
        self.assertEqual(3, receipt.tool_calls)
        self.assertEqual(1, receipt.schema_calls)
        self.assertEqual(1, receipt.sql_attempts)
        self.assertEqual(30, receipt.prompt_tokens)
        self.assertEqual(15, receipt.completion_tokens)
        self.assertIn("model_request", raw)
        self.assertIn("agent_tool_result", raw)
        self.assertIn("SELECT COUNT(*)", raw)
        serialized = json.dumps(
            factorial.asdict(receipt),
            sort_keys=True,
        )
        self.assertNotIn("How many orders", serialized)
        self.assertNotIn("SELECT COUNT", serialized)

    def test_executed_sql_is_not_implicitly_submitted(self):
        task = factorial.RuntimeTask(
            task_id="task-1",
            database="fixture",
            query_category="basic",
            question="How many orders exist?",
            instructions="",
            gold_sql="SELECT COUNT(*) FROM orders",
        )
        executor = FakeExecutor()
        with tempfile.TemporaryDirectory() as temporary:
            raw_path = pathlib.Path(temporary) / "raw.jsonl"
            with patch.object(
                factorial,
                "results_equal",
            ) as equality:
                receipt = factorial.run_agent(
                    task=task,
                    arm="no_skill",
                    seed=7,
                    api=NoSubmissionAPI(),
                    executor=executor,
                    limits=factorial.AgentLimits(),
                    raw_audit_path=raw_path,
                )
        self.assertEqual("none", receipt.terminal_action)
        self.assertEqual("no_terminal_submission", receipt.outcome)
        self.assertFalse(receipt.semantic_correct)
        self.assertIsNone(receipt.candidate_sql_sha256)
        self.assertEqual(1, len(receipt.attempt_receipts))
        self.assertEqual(1, executor.candidate_executions)
        equality.assert_not_called()

    def test_sql_budget_exhaustion_switches_to_terminal_only_tools(self):
        task = factorial.RuntimeTask(
            task_id="task-1",
            database="fixture",
            query_category="basic",
            question="Return the requested value.",
            instructions="",
            gold_sql="SELECT 4 AS n",
        )
        api = TerminalBudgetAPI()
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(
                factorial,
                "results_equal",
                return_value=True,
            ):
                receipt = factorial.run_agent(
                    task=task,
                    arm="no_skill",
                    seed=7,
                    api=api,
                    executor=FakeExecutor(),
                    limits=factorial.AgentLimits(
                        max_sql_attempts=3,
                        max_model_turns=6,
                    ),
                    raw_audit_path=(
                        pathlib.Path(temporary) / "raw.jsonl"
                    ),
                )
        self.assertEqual("submit_sql", receipt.terminal_action)
        self.assertEqual(3, receipt.sql_attempts)
        self.assertEqual(
            list(factorial.ALL_TOOL_NAMES)
            if hasattr(factorial, "ALL_TOOL_NAMES")
            else [
                "describe_schema",
                "execute_sql",
                "submit_sql",
                "abstain",
            ],
            api.offered_tool_names[-2],
        )
        self.assertEqual(
            ["submit_sql", "abstain"],
            api.offered_tool_names[-1],
        )

    def test_abstain_is_an_explicit_terminal_action(self):
        task = factorial.RuntimeTask(
            task_id="task-1",
            database="fixture",
            query_category="basic",
            question="How many orders exist?",
            instructions="",
            gold_sql="SELECT COUNT(*) FROM orders",
        )
        executor = FakeExecutor()
        with tempfile.TemporaryDirectory() as temporary:
            receipt = factorial.run_agent(
                task=task,
                arm="no_skill",
                seed=7,
                api=AbstainAPI(),
                executor=executor,
                limits=factorial.AgentLimits(),
                raw_audit_path=pathlib.Path(temporary) / "raw.jsonl",
            )
        self.assertEqual("abstain", receipt.terminal_action)
        self.assertEqual(
            "abstained:insufficient_schema",
            receipt.outcome,
        )
        self.assertEqual(
            "insufficient_schema",
            receipt.abstain_reason_code,
        )
        self.assertFalse(receipt.execution_completed)
        self.assertIsNone(receipt.policy_accepted)
        self.assertEqual(0, executor.candidate_executions)

    def test_dropped_native_tool_call_is_a_protocol_failure(self):
        task = factorial.RuntimeTask(
            task_id="task-1",
            database="fixture",
            query_category="basic",
            question="How many orders exist?",
            instructions="",
            gold_sql="SELECT COUNT(*) FROM orders",
        )
        with tempfile.TemporaryDirectory() as temporary:
            receipt = factorial.run_agent(
                task=task,
                arm="no_skill",
                seed=7,
                api=DroppedToolAPI(),
                executor=FakeExecutor(),
                limits=factorial.AgentLimits(),
                raw_audit_path=pathlib.Path(temporary) / "raw.jsonl",
            )
        self.assertEqual(
            "tool_parser_dropped_tool_calls",
            receipt.protocol_failure_code,
        )
        self.assertEqual(
            "tool_protocol_failure:tool_parser_dropped_tool_calls",
            receipt.outcome,
        )

    def test_aggregate_preserves_outcome_counts(self):
        attempt = factorial.AttemptReceipt(
            attempt_id="attempt_opaque",
            attempt_index=0,
            sql_sha256="b" * 64,
            authority_valid=True,
            policy_accepted=True,
            execution_completed=True,
            unauthorized_observation=False,
            status="ok",
            policy_error_code=None,
            error_class=None,
            result_sha256="e" * 64,
            row_count=1,
            column_count=1,
        )
        common = dict(
            task_id_sha256="a" * 64,
            seed=1,
            authority_valid=True,
            policy_accepted=True,
            execution_completed=True,
            unauthorized_observation=False,
            terminal_action="submit_sql",
            submitted_attempt_id="attempt_opaque",
            abstain_reason_code=None,
            protocol_failure_code=None,
            policy_error_code=None,
            candidate_sql_sha256="b" * 64,
            final_answer_sha256="c" * 64,
            attempt_receipts=(attempt,),
            attempt_receipt_chain_sha256="f" * 64,
            authority_binding_sha256="1" * 64,
            authority_epoch_ref_sha256="2" * 64,
            authority_snapshot_sha256="3" * 64,
            model_calls=2,
            tool_calls=2,
            schema_calls=1,
            sql_attempts=1,
            successful_sql_attempts=1,
            prompt_tokens=100,
            completion_tokens=20,
            elapsed_ms=10.0,
            system_fingerprint="runtime",
            raw_audit_sha256="d" * 64,
        )
        receipts = [
            factorial.RunReceipt(
                arm="no_skill",
                semantic_correct=True,
                strict_answer_shape_correct=True,
                outcome="semantic_correct",
                **common,
            ),
            factorial.RunReceipt(
                arm="no_skill",
                semantic_correct=False,
                strict_answer_shape_correct=False,
                outcome="semantic_incorrect",
                **common,
            ),
        ]
        aggregate = factorial._aggregate(receipts)["no_skill"]
        self.assertEqual(2, aggregate["tasks"])
        self.assertEqual(1, aggregate["semantic_correct"])
        self.assertEqual(
            {"semantic_correct": 1, "semantic_incorrect": 1},
            aggregate["outcomes"],
        )


if __name__ == "__main__":
    unittest.main()
