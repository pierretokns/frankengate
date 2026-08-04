from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))

from trace2skill_source_replay_overlap_audit import run
from frontier_transfer_multiseed_aggregate import run as aggregate_run


def write_event(root: Path, name: str, task_id: str) -> None:
    (root / name).write_text(
        json.dumps({"event": "factorial_task_start", "task_id": task_id}) + "\n",
        encoding="utf-8",
    )


class Trace2SkillOverlapAuditTest(unittest.TestCase):
    def test_overlap_is_contamination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            replay = root / "replay"
            source.mkdir()
            replay.mkdir()
            write_event(source, "source.jsonl", "task-a")
            write_event(replay, "replay.jsonl", "task-a")
            result = run([source], [replay])
            self.assertTrue(result["contaminated"])
            self.assertEqual(result["overlap_task_count"], 1)

    def test_disjoint_is_not_contamination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            replay = root / "replay"
            source.mkdir()
            replay.mkdir()
            write_event(source, "source.jsonl", "task-a")
            write_event(replay, "replay.jsonl", "task-b")
            result = run([source], [replay])
            self.assertFalse(result["contaminated"])
            self.assertEqual(result["overlap_task_count"], 0)

    def test_family_disjoint_aggregate_rejects_contaminated_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "result.json"
            verification_path = root / "verification.json"
            audit_path = root / "audit.json"
            result_path.write_text(
                json.dumps(
                    {
                        "classification": "family_disjoint_transfer",
                        "protocol_remediation": {"id": "family-disjoint-v1", "seed_base": 1},
                        "dataset": {"task_id_sha256": ["task-a"]},
                        "arms": {"no_skill": {}},
                        "task_runs": [
                            {
                                "task_id_sha256": "task-a",
                                "arm": "no_skill",
                                "semantic_correct": True,
                                "terminal_action": "submit_sql",
                                "unauthorized_observation": False,
                                "authority_valid": True,
                                "sql_attempts": 1,
                                "tool_calls": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            verification_path.write_text(
                json.dumps({"semantic_verification_passed": True}), encoding="utf-8"
            )
            audit_path.write_text(
                json.dumps(
                    {
                        "schema_version": "frankengate-trace2skill-source-replay-overlap-v1",
                        "source": {"task_count": 1},
                        "replay": {"task_count": 1},
                        "overlap_task_count": 1,
                        "contaminated": True,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                aggregate_run([result_path], [verification_path], [audit_path])

    def test_family_disjoint_aggregate_records_zero_overlap_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "result.json"
            verification_path = root / "verification.json"
            audit_path = root / "audit.json"
            result_path.write_text(
                json.dumps(
                    {
                        "classification": "family_disjoint_transfer",
                        "protocol_remediation": {"id": "family-disjoint-v1", "seed_base": 1},
                        "dataset": {"task_id_sha256": ["task-a"]},
                        "arms": {"no_skill": {}},
                        "task_runs": [
                            {
                                "task_id_sha256": "task-a",
                                "arm": "no_skill",
                                "semantic_correct": True,
                                "terminal_action": "submit_sql",
                                "unauthorized_observation": False,
                                "authority_valid": True,
                                "sql_attempts": 1,
                                "tool_calls": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            verification_path.write_text(
                json.dumps({"semantic_verification_passed": True}), encoding="utf-8"
            )
            audit_path.write_text(
                json.dumps(
                    {
                        "schema_version": "frankengate-trace2skill-source-replay-overlap-v1",
                        "source": {"task_count": 1},
                        "replay": {"task_count": 1},
                        "overlap_task_count": 0,
                        "contaminated": False,
                    }
                ),
                encoding="utf-8",
            )
            result = aggregate_run([result_path], [verification_path], [audit_path])
            self.assertTrue(result["source_replay_disjoint_verified"])
