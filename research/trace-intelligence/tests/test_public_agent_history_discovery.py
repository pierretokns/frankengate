import json
import tempfile
import unittest
from pathlib import Path

from public_agent_history_discovery import DiscoveryError, build_result


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"


class PublicAgentHistoryDiscoveryTests(unittest.TestCase):
    def test_builds_content_free_pinned_receipt(self):
        result = build_result(CONFIG_DIR)
        self.assertEqual(
            359,
            result["discovery_scale"][
                "hugging_face_agent_trace_dataset_hits"
            ],
        )
        self.assertEqual(
            1,
            len(result["classification"]["near_complete_home_state"]),
        )
        self.assertEqual(
            9,
            result["security_observation"][
                "codex_repositories_with_auth_adjacent"
            ],
        )
        self.assertEqual(
            2,
            len(
                result["classification"][
                    "paired_trace_and_memory_strata"
                ]
            ),
        )
        self.assertFalse(result["raw_content_committed"])
        self.assertFalse(result["candidate_values_emitted"])
        self.assertEqual(64, len(result["result_sha256"]))

    def test_rejects_impossible_auth_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "datasets").mkdir()
            for path in CONFIG_DIR.glob("*.json"):
                (tmp_path / path.name).write_bytes(path.read_bytes())
            for path in (CONFIG_DIR / "datasets").glob("*.json"):
                (tmp_path / "datasets" / path.name).write_bytes(
                    path.read_bytes()
                )
            discovery_path = (
                tmp_path / "public-agent-history-discovery.json"
            )
            value = json.loads(discovery_path.read_text())
            value["github"]["codex_top_repositories_with_auth_adjacent"] = 11
            discovery_path.write_text(json.dumps(value))
            with self.assertRaises(DiscoveryError):
                build_result(tmp_path)


if __name__ == "__main__":
    unittest.main()
