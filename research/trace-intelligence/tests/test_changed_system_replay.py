import json
import hashlib
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
)
from changed_system_replay import (  # noqa: E402
    BenignAuditSystem,
    HarmfulDropSystem,
    OriginalReplaySystem,
    ReplayTask,
    build_input_manifest,
    run_changed_system_experiment,
)
from agentevals_interop.experiment import CohortCase  # noqa: E402


def example_task() -> ReplayTask:
    return ReplayTask.from_natural_trajectory(
        NaturalTrajectory(
            source_sha256="a" * 64,
            user_text="Inspect, repair, and verify.",
            final_response="The service is healthy.",
            tool_calls=(
                NaturalToolCall(
                    call_id="call-1",
                    name="Inspect",
                    arguments={"target": "service"},
                    result={"healthy": False},
                    result_observed=True,
                ),
                NaturalToolCall(
                    call_id="call-2",
                    name="Repair",
                    arguments={"target": "service"},
                    result={"healthy": True},
                    result_observed=True,
                ),
            ),
        )
    )


class ChangedSystemReplayTest(unittest.TestCase):
    def test_original_system_executes_and_resets_the_source_derived_program(self):
        task = example_task()
        system = OriginalReplaySystem()

        first = system.execute(task)
        second = system.execute(task)

        self.assertEqual(first.trajectory, second.trajectory)
        self.assertEqual(2, system.reset_count)
        self.assertEqual(0, first.state_before.completed_transition_count)
        self.assertEqual(2, first.state_after.completed_transition_count)
        self.assertTrue(first.outcome.completed)
        self.assertEqual("all_source_transitions_applied", first.outcome.reason)
        self.assertEqual(
            ["Inspect", "Repair"],
            [call.name for call in first.trajectory.tool_calls],
        )
        self.assertEqual(
            [{"healthy": False}, {"healthy": True}],
            [call.result for call in first.trajectory.tool_calls],
        )

    def test_benign_and_harmful_implementations_change_runtime_behavior(self):
        task = example_task()

        benign = BenignAuditSystem().execute(task)
        harmful = HarmfulDropSystem().execute(task)

        self.assertTrue(benign.outcome.completed)
        self.assertEqual(3, len(benign.trajectory.tool_calls))
        self.assertEqual("FrankengateAudit", benign.trajectory.tool_calls[-1].name)
        self.assertEqual(
            task.expected_final_response,
            benign.trajectory.final_response,
        )
        self.assertFalse(harmful.outcome.completed)
        self.assertEqual(1, harmful.state_after.completed_transition_count)
        self.assertEqual(1, len(harmful.trajectory.tool_calls))
        self.assertNotEqual(
            task.expected_final_response,
            harmful.trajectory.final_response,
        )
        self.assertNotEqual(
            benign.trajectory,
            harmful.trajectory,
        )

    @unittest.skipUnless(
        os.environ.get("AGENTEVALS_UPSTREAM_PYTHON"),
        "set AGENTEVALS_UPSTREAM_PYTHON to exercise pinned upstream AgentEvals",
    )
    def test_real_upstream_assertions_score_executed_system_implementations(self):
        task = example_task()
        upstream_python = Path(os.environ["AGENTEVALS_UPSTREAM_PYTHON"])
        upstream_root = Path(os.environ["AGENTEVALS_UPSTREAM_ROOT"])

        with tempfile.TemporaryDirectory() as temporary:
            result = run_changed_system_experiment(
                tasks=(task,),
                upstream_python=upstream_python,
                upstream_root=upstream_root,
                raw_dir=Path(temporary),
            )

        cells = {
            (row["implementation"], row["assertion"]): row
            for row in result["assertion_results"]
        }
        for assertion in ("EXACT", "IN_ORDER", "ANY_ORDER"):
            self.assertEqual(
                1,
                cells[("original", assertion)]["passed"],
            )
            self.assertEqual(
                1,
                cells[("harmful_drop", assertion)]["failed"],
            )
        self.assertEqual(1, cells[("benign_audit", "EXACT")]["failed"])
        self.assertEqual(1, cells[("benign_audit", "IN_ORDER")]["passed"])
        self.assertEqual(1, cells[("benign_audit", "ANY_ORDER")]["passed"])
        self.assertTrue(result["changed_system_executed"])
        self.assertFalse(result["source_environment_executed"])
        self.assertEqual(
            "resettable_opaque_transition_replay",
            result["claim_boundary"],
        )
        self.assertTrue(
            result["upstream"]["runtime_attestation"][
                "agentevals_loaded_from_pinned_checkout"
            ]
        )
        self.assertEqual(
            "2.1.0",
            result["upstream"]["runtime_attestation"]["google_adk_version"],
        )
        self.assertEqual(0, result["outcomes"]["harmful_drop"]["completed"])
        self.assertEqual(1, result["outcomes"]["original"]["completed"])
        self.assertEqual(1, result["outcomes"]["benign_audit"]["completed"])
        serialized = json.dumps(result)
        self.assertNotIn(task.user_text, serialized)
        self.assertNotIn(task.expected_final_response, serialized)
        self.assertNotIn("call-1", serialized)
        self.assertNotIn(str(upstream_root), serialized)

    def test_input_manifest_requires_the_pinned_hugging_face_revision(self):
        task = example_task()
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            source = cache / "transcripts" / "project" / "session.jsonl"
            source.parent.mkdir(parents=True)
            source.write_text("{}\n", encoding="utf-8")
            metadata = (
                cache
                / ".cache"
                / "huggingface"
                / "download"
                / "transcripts"
                / "project"
                / "session.jsonl.metadata"
            )
            metadata.parent.mkdir(parents=True)
            metadata.write_text(
                "pinned-revision\ncontent-etag\n123.0\n",
                encoding="utf-8",
            )
            dataset_manifest = cache / "dataset.json"
            dataset_manifest.write_text(
                json.dumps(
                    {
                        "dataset_id": "example/wisp",
                        "dataset_revision": "pinned-revision",
                        "license": "MIT",
                    }
                ),
                encoding="utf-8",
            )
            case = CohortCase(
                case_id="case-1",
                source_path=source,
                trajectory=NaturalTrajectory(
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    user_text=task.user_text,
                    final_response=task.expected_final_response,
                    tool_calls=task.expected_calls,
                ),
            )

            manifest = build_input_manifest(
                cohort=(case,),
                cache_root=cache,
                dataset_manifest_path=dataset_manifest,
            )
            metadata.write_text(
                "wrong-revision\ncontent-etag\n123.0\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "revision mismatch"):
                build_input_manifest(
                    cohort=(case,),
                    cache_root=cache,
                    dataset_manifest_path=dataset_manifest,
                )

        self.assertEqual("pinned-revision", manifest["dataset_revision"])
        self.assertEqual(1, len(manifest["selected_inputs"]))
        self.assertEqual(
            hashlib.sha256(b"{}\n").hexdigest(),
            manifest["selected_inputs"][0]["source_sha256"],
        )
        serialized = json.dumps(manifest)
        self.assertNotIn(str(cache), serialized)
        self.assertNotIn(task.user_text, serialized)
        self.assertNotIn(task.expected_final_response, serialized)

    def test_committed_aggregate_is_content_minimized_and_integrity_linked(self):
        result_path = (
            ROOT
            / "experiments"
            / "results"
            / "changed-system-replay-wisp-2026-07-30.json"
        )
        manifest_path = (
            ROOT
            / "experiments"
            / "manifests"
            / "changed-system-replay-wisp-2026-07-30.json"
        )
        result = json.loads(result_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        claimed_result_hash = result.pop("result_sha256")
        actual_result_hash = hashlib.sha256(
            json.dumps(
                result,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(claimed_result_hash, actual_result_hash)
        self.assertEqual(
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            result["input_manifest"]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "changed_system_replay.py").read_bytes()).hexdigest(),
            result["implementation_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "changed_system_replay_run.py").read_bytes()
            ).hexdigest(),
            result["runner_sha256"],
        )
        self.assertEqual(
            [item["case_id"] for item in manifest["selected_inputs"]],
            [item["case_id"] for item in result["cases"]],
        )
        serialized = result_path.read_text(encoding="utf-8")
        self.assertNotIn("/private/", serialized)
        self.assertNotIn("/Users/", serialized)
        self.assertFalse(manifest["raw_content_committed"])
        self.assertFalse(result["raw_artifacts_committed"])


if __name__ == "__main__":
    unittest.main()
