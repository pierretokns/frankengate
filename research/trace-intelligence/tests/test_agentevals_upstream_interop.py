import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agentevals_interop.experiment import (  # noqa: E402
    NaturalToolCall,
    NaturalTrajectory,
    build_eval_set,
    build_otlp_export,
    extract_wisp_trajectory,
    mutate_trajectory,
    run_upstream_experiment,
    select_wisp_cohort,
)


class AgentEvalsUpstreamInteropTest(unittest.TestCase):
    def test_extracts_one_natural_wisp_turn_with_paired_tool_calls(self):
        records = [
            {
                "type": "user",
                "uuid": "user-1",
                "timestamp": "2026-06-12T20:02:50.648Z",
                "message": {"role": "user", "content": "Inspect, repair, then verify."},
            },
            {
                "type": "assistant",
                "uuid": "assistant-1",
                "timestamp": "2026-06-12T20:03:01.546Z",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call-1",
                            "name": "Inspect",
                            "input": {"target": "service"},
                        },
                        {
                            "type": "tool_use",
                            "id": "call-2",
                            "name": "Repair",
                            "input": {"target": "service"},
                        },
                    ],
                },
            },
            {
                "type": "user",
                "uuid": "tool-result-1",
                "timestamp": "2026-06-12T20:03:02.590Z",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call-1",
                            "content": "unhealthy",
                            "is_error": False,
                        },
                        {
                            "type": "tool_result",
                            "tool_use_id": "call-2",
                            "content": "healthy",
                            "is_error": False,
                        },
                    ],
                },
            },
            {
                "type": "assistant",
                "uuid": "assistant-2",
                "timestamp": "2026-06-12T20:03:07.591Z",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "The service is healthy."}],
                },
            },
        ]

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "session.jsonl"
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            trajectory = extract_wisp_trajectory(path)

        self.assertEqual("Inspect, repair, then verify.", trajectory.user_text)
        self.assertEqual("The service is healthy.", trajectory.final_response)
        self.assertEqual(["Inspect", "Repair"], [call.name for call in trajectory.tool_calls])
        self.assertEqual(["call-1", "call-2"], [call.call_id for call in trajectory.tool_calls])
        self.assertEqual(
            [{"target": "service"}, {"target": "service"}],
            [call.arguments for call in trajectory.tool_calls],
        )
        self.assertEqual(["unhealthy", "healthy"], [call.result for call in trajectory.tool_calls])
        self.assertTrue(all(call.result_observed for call in trajectory.tool_calls))
        self.assertEqual(64, len(trajectory.source_sha256))

    def test_projects_natural_trajectory_to_real_otlp_and_adk_eval_set_contracts(self):
        trajectory = NaturalTrajectory(
            source_sha256="a" * 64,
            user_text="Inspect, repair, then verify.",
            final_response="The service is healthy.",
            tool_calls=(
                NaturalToolCall(
                    call_id="call-1",
                    name="Inspect",
                    arguments={"target": "service"},
                    result="unhealthy",
                    result_observed=True,
                ),
                NaturalToolCall(
                    call_id="call-2",
                    name="Repair",
                    arguments={"target": "service"},
                    result="healthy",
                    result_observed=True,
                ),
            ),
        )

        otlp = build_otlp_export(trajectory, arm="baseline")
        eval_set = build_eval_set(trajectory)

        resource = otlp["resourceSpans"][0]
        spans = resource["scopeSpans"][0]["spans"]
        self.assertEqual(4, len(spans))
        self.assertEqual(32, len(spans[0]["traceId"]))
        self.assertEqual("invoke_agent frankengate_wisp", spans[0]["name"])
        self.assertEqual(spans[0]["spanId"], spans[1]["parentSpanId"])
        self.assertEqual(
            ["Inspect", "Repair"],
            [
                next(
                    attribute["value"]["stringValue"]
                    for attribute in span["attributes"]
                    if attribute["key"] == "gen_ai.tool.name"
                )
                for span in spans[2:]
            ],
        )

        invocation = eval_set["eval_cases"][0]["conversation"][0]
        self.assertEqual(
            ["Inspect", "Repair"],
            [
                call["name"]
                for call in invocation["intermediate_data"]["tool_uses"]
            ],
        )
        self.assertEqual(
            "The service is healthy.",
            invocation["final_response"]["parts"][0]["text"],
        )
        self.assertNotIn("a" * 64, json.dumps(otlp))

    def test_mutation_arms_separate_benign_representation_from_harmful_changes(self):
        trajectory = NaturalTrajectory(
            source_sha256="b" * 64,
            user_text="Inspect, repair, then verify.",
            final_response="The service is healthy.",
            tool_calls=(
                NaturalToolCall(
                    call_id="call-1",
                    name="Inspect",
                    arguments={"target": "service"},
                    result="unhealthy",
                    result_observed=True,
                ),
                NaturalToolCall(
                    call_id="call-2",
                    name="Repair",
                    arguments={"target": "service"},
                    result="healthy",
                    result_observed=True,
                ),
            ),
        )

        remapped = mutate_trajectory(trajectory, "benign_id_remap")
        self.assertEqual(
            [call.name for call in trajectory.tool_calls],
            [call.name for call in remapped.tool_calls],
        )
        self.assertEqual(
            [call.arguments for call in trajectory.tool_calls],
            [call.arguments for call in remapped.tool_calls],
        )
        self.assertNotEqual(
            [call.call_id for call in trajectory.tool_calls],
            [call.call_id for call in remapped.tool_calls],
        )

        dropped = mutate_trajectory(trajectory, "harmful_tool_drop")
        self.assertEqual(1, len(dropped.tool_calls))
        self.assertEqual("Inspect", dropped.tool_calls[0].name)

        corrupted = mutate_trajectory(trajectory, "harmful_argument_corruption")
        self.assertNotEqual(
            trajectory.tool_calls[0].arguments,
            corrupted.tool_calls[0].arguments,
        )
        self.assertEqual(
            trajectory.tool_calls[1].arguments,
            corrupted.tool_calls[1].arguments,
        )

        paraphrased = mutate_trajectory(trajectory, "benign_response_wrapper")
        self.assertIn(trajectory.final_response, paraphrased.final_response)

        reversed_outcome = mutate_trajectory(trajectory, "harmful_response_reversal")
        self.assertNotIn(trajectory.final_response, reversed_outcome.final_response)
        self.assertIn("failed", reversed_outcome.final_response.lower())

    def test_selects_a_deterministic_complete_natural_tool_cohort(self):
        def write_session(path: Path, tool_count: int, include_final: bool = True):
            records = [
                {
                    "type": "user",
                    "message": {"role": "user", "content": f"Task for {path.stem}"},
                },
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": f"call-{index}",
                                "name": f"Tool{index}",
                                "input": {"index": index},
                            }
                            for index in range(tool_count)
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
                                "tool_use_id": f"call-{index}",
                                "content": {"ok": True},
                            }
                            for index in range(tool_count)
                        ],
                    },
                },
            ]
            if include_final:
                records.append(
                    {
                        "type": "assistant",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "Task completed."}],
                        },
                    }
                )
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_session(root / "eligible-b.jsonl", 3)
            write_session(root / "eligible-a.jsonl", 2)
            write_session(root / "one-tool.jsonl", 1)
            write_session(root / "no-final.jsonl", 2, include_final=False)

            first = select_wisp_cohort(root, max_cases=2)
            second = select_wisp_cohort(root, max_cases=2)

        self.assertEqual(
            [case.case_id for case in first],
            [case.case_id for case in second],
        )
        self.assertEqual(2, len(first))
        self.assertTrue(all(len(case.trajectory.tool_calls) >= 2 for case in first))
        self.assertTrue(
            all(
                call.result_observed
                for case in first
                for call in case.trajectory.tool_calls
            )
        )
        self.assertTrue(all(len(case.case_id) == 24 for case in first))

    @unittest.skipUnless(
        os.environ.get("AGENTEVALS_UPSTREAM_PYTHON"),
        "set AGENTEVALS_UPSTREAM_PYTHON to run the pinned upstream library",
    )
    def test_executes_pinned_upstream_matchers_over_mutation_arms(self):
        trajectory = NaturalTrajectory(
            source_sha256="c" * 64,
            user_text="Inspect the service, repair it, and verify the outcome.",
            final_response="The service is healthy.",
            tool_calls=(
                NaturalToolCall(
                    call_id="call-1",
                    name="Inspect",
                    arguments={"target": "service"},
                    result="unhealthy",
                    result_observed=True,
                ),
                NaturalToolCall(
                    call_id="call-2",
                    name="Repair",
                    arguments={"target": "service"},
                    result="healthy",
                    result_observed=True,
                ),
            ),
        )
        upstream_python = Path(os.environ["AGENTEVALS_UPSTREAM_PYTHON"])
        upstream_root = Path(
            os.environ.get(
                "AGENTEVALS_UPSTREAM_ROOT",
                str(upstream_python.parent.parent),
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            aggregate = run_upstream_experiment(
                trajectories=(trajectory,),
                upstream_python=upstream_python,
                upstream_root=upstream_root,
                raw_dir=Path(temporary),
                arms=(
                    "baseline",
                    "benign_id_remap",
                    "sequence_reversal",
                    "harmful_tool_drop",
                    "harmful_argument_corruption",
                ),
                include_semantic=False,
            )

        cells = {
            (row["arm"], row["assertion"]): row
            for row in aggregate["deterministic_assertions"]
        }
        for assertion in ("EXACT", "IN_ORDER", "ANY_ORDER"):
            self.assertEqual(1.0, cells[("baseline", assertion)]["mean_score"])
            self.assertEqual(
                1.0,
                cells[("benign_id_remap", assertion)]["mean_score"],
            )
            self.assertEqual(
                0.0,
                cells[("harmful_tool_drop", assertion)]["mean_score"],
            )
            self.assertEqual(
                0.0,
                cells[("harmful_argument_corruption", assertion)]["mean_score"],
            )

        self.assertEqual(0.0, cells[("sequence_reversal", "EXACT")]["mean_score"])
        self.assertEqual(
            0.0,
            cells[("sequence_reversal", "IN_ORDER")]["mean_score"],
        )
        self.assertEqual(
            1.0,
            cells[("sequence_reversal", "ANY_ORDER")]["mean_score"],
        )
        self.assertEqual("stored_trace_assertion_only", aggregate["claim_boundary"])
        self.assertEqual("0.9.7", aggregate["upstream"]["package_version"])
        serialized = json.dumps(aggregate)
        self.assertNotIn(trajectory.user_text, serialized)
        self.assertNotIn(trajectory.final_response, serialized)
        self.assertNotIn("call-1", serialized)
        self.assertNotIn(str(upstream_root), serialized)

    @unittest.skipUnless(
        os.environ.get("AGENTEVALS_JUDGE_BASE_URL")
        and os.environ.get("AGENTEVALS_UPSTREAM_PYTHON"),
        "set the upstream Python and a loopback judge URL for semantic assertions",
    )
    def test_executes_upstream_semantic_response_judge_on_benign_and_harmful_changes(
        self,
    ):
        trajectory = NaturalTrajectory(
            source_sha256="d" * 64,
            user_text="Switch to workspace three and verify it.",
            final_response="Workspace 3 is active and the change was verified.",
            tool_calls=(
                NaturalToolCall(
                    call_id="call-1",
                    name="Bash",
                    arguments={"command": "switch 3"},
                    result="workspace 3 active",
                    result_observed=True,
                ),
                NaturalToolCall(
                    call_id="call-2",
                    name="Bash",
                    arguments={"command": "verify"},
                    result="workspace 3",
                    result_observed=True,
                ),
            ),
        )
        upstream_python = Path(os.environ["AGENTEVALS_UPSTREAM_PYTHON"])
        upstream_root = Path(os.environ["AGENTEVALS_UPSTREAM_ROOT"])
        with tempfile.TemporaryDirectory() as temporary:
            aggregate = run_upstream_experiment(
                trajectories=(trajectory,),
                upstream_python=upstream_python,
                upstream_root=upstream_root,
                raw_dir=Path(temporary),
                arms=(
                    "baseline",
                    "benign_response_wrapper",
                    "harmful_response_reversal",
                ),
                include_semantic=True,
                judge_model="openai/default_model",
                judge_base_url=os.environ["AGENTEVALS_JUDGE_BASE_URL"],
                judge_api_key="local-no-secret",
            )

        cells = {
            row["arm"]: row for row in aggregate["semantic_assertions"]
        }
        self.assertEqual(1, cells["baseline"]["passed"])
        self.assertEqual(1, cells["benign_response_wrapper"]["passed"])
        self.assertEqual(1, cells["harmful_response_reversal"]["failed"])
        self.assertEqual(0, sum(row["errored"] for row in cells.values()))
        serialized = json.dumps(aggregate)
        self.assertNotIn("local-no-secret", serialized)
        self.assertNotIn(os.environ["AGENTEVALS_JUDGE_BASE_URL"], serialized)


if __name__ == "__main__":
    unittest.main()
