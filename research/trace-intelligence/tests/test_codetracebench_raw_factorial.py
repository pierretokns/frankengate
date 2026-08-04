import dataclasses
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

import codetracebench_raw_factorial as MODULE  # noqa: E402


class FormatAdapterTest(unittest.TestCase):
    def test_miniswe_pairs_bash_action_with_next_terminal_result(self):
        members = {
            "run/mini.traj.json": json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "task"},
                        {
                            "role": "assistant",
                            "content": "```bash\npytest -q\n```",
                            "timestamp": "t1",
                        },
                        {
                            "role": "user",
                            "content": "<returncode>1</returncode>\nfailed",
                        },
                    ]
                }
            ).encode()
        }
        steps, variant, losses = MODULE._parse_miniswe(members)
        self.assertEqual("miniswe_traj_json_bash_v1", variant)
        self.assertEqual(1, len(steps))
        self.assertEqual("pytest -q", steps[0].action)
        self.assertIn("<returncode>1</returncode>", steps[0].observation)
        self.assertTrue(any("authorization" in loss for loss in losses))

    def test_terminus_retains_prompt_only_tail_without_mapping_it(self):
        members = {
            "run/agent-logs/episode-0/response.txt": json.dumps(
                {"commands": [{"keystrokes": "ls"}]}
            ).encode(),
            "run/agent-logs/episode-1/response.txt": json.dumps(
                {"commands": [{"keystrokes": "pytest"}]}
            ).encode(),
            "run/agent-logs/episode-1/prompt.txt": b"New Terminal Output:\nfiles",
            "run/agent-logs/episode-2/prompt.txt": b"New Terminal Output:\nfailed",
            "run/agent-logs/episode-3/prompt.txt": b"New Terminal Output:\nlate tail",
        }
        steps, variant, losses = MODULE._parse_terminus(
            members, manifest_step_count=2
        )
        self.assertEqual("terminus2_episode_pair_v2", variant)
        self.assertEqual(3, len(steps))
        self.assertEqual([1, 2, None], [step.manifest_step_id for step in steps])
        self.assertEqual("files", steps[0].observation)
        self.assertEqual("", steps[2].action)
        self.assertTrue(
            any("1 native tail steps" in loss for loss in losses), losses
        )

    def test_tensorblock_mapping_retains_excluded_native_calls(self):
        def record(timestamp, name):
            return json.dumps(
                {
                    "timestamp": timestamp,
                    "response": {
                        "choices": [
                            {
                                "message": {
                                    "tool_calls": [
                                        {
                                            "function": {
                                                "name": name,
                                                "arguments": "{}",
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    "messages": [],
                }
            ).encode()

        members = {
            "run/tensorblock-1.json": record(1, "task_tracker"),
            "run/tensorblock-2.json": record(2, "terminal"),
            "run/tensorblock-3.json": record(3, "finish"),
        }
        steps, variant, losses = MODULE._parse_openhands_tensorblocks(
            members, manifest_step_count=1
        )
        self.assertIn("drop_initial_planning_and_terminal_finish", variant)
        self.assertEqual(3, len(steps))
        self.assertEqual([None, 1, None], [step.manifest_step_id for step in steps])
        self.assertTrue(any("2 native calls" in loss for loss in losses))


class IntegrityAndScoringTest(unittest.TestCase):
    def test_archive_hash_mismatch_fails_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "artifact.tar.zst"
            path.write_bytes(b"not the admitted archive")
            with self.assertRaisesRegex(ValueError, "immutable hash mismatch"):
                MODULE.parse_archive(
                    path,
                    traj_id="t",
                    agent="SWE-agent",
                    manifest_step_count=1,
                    expected_sha256="0" * 64,
                )

    def test_factor_ranking_is_independent_of_verifier_state(self):
        steps = [
            MODULE._make_step(1, 1, "ls", "ok"),
            MODULE._make_step(2, 2, "pytest", "ERROR: test failed"),
        ]
        trajectory = MODULE.ParsedTrajectory(
            traj_id="t",
            agent="agent",
            steps=tuple(steps),
            manifest_step_count=2,
            native_step_count=2,
            mapped_step_count=2,
            alignment_status="exact",
            parser_variant="synthetic",
            action_coverage=1.0,
            observation_coverage=1.0,
            timestamp_coverage=0.0,
            relevant_member_count=0,
            relevant_uncompressed_bytes=0,
            archive_sha256="0" * 64,
            verifier=MODULE.VerifierEvidence(True, True, False, "synthetic"),
            losses=(),
        )
        before = MODULE._factorial_ranking(
            MODULE._mapped_steps(trajectory),
            invariants=True,
            topology=True,
            judge=True,
        )
        after = MODULE._factorial_ranking(
            MODULE._mapped_steps(
                dataclasses.replace(
                    trajectory,
                    verifier=dataclasses.replace(
                        trajectory.verifier, outcome=True
                    ),
                )
            ),
            invariants=True,
            topology=True,
            judge=True,
        )
        self.assertEqual([2, 1], before)
        self.assertEqual(before, after)

    def test_allowed_tail_exposes_exact_sequence_brittleness(self):
        steps = (
            MODULE._make_step(1, 1, "ls", "ok"),
            MODULE._make_step(2, 2, "pytest", "ok"),
        )
        expected = MODULE.AuditState(steps, True)
        observed = MODULE._mutate_state(
            expected,
            {1},
            "inject_benign_tail",
            seed=7,
            traj_id="t",
        )
        self.assertIsNotNone(observed)
        self.assertFalse(
            MODULE._assertion_passes(
                "exact_sequence", expected, observed, {1}
            )
        )
        self.assertTrue(
            MODULE._assertion_passes(
                "ordered_gold_action", expected, observed, {1}
            )
        )


if __name__ == "__main__":
    unittest.main()
