import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import real_user_analysis_arms as MODULE


def write_jsonl(path: Path, records: list[dict], malformed: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = "".join(json.dumps(record) + "\n" for record in records)
    if malformed:
        serialized += "{malformed SECRET MALFORMED CONTENT"
    path.write_text(serialized, encoding="utf-8")


def tool_use(node, parent, call, name):
    return {
        "type": "assistant",
        "uuid": node,
        "parentUuid": parent,
        "timestamp": "2026-01-01T00:00:00Z",
        "cwd": "/SECRET/HOME/PRIVATE/PROJECT",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": call,
                    "name": name,
                    "input": {"command": "SECRET COMMAND"},
                },
                {"type": "thinking", "thinking": "SECRET REASONING"},
            ],
        },
    }


def tool_result(node, parent, call, is_error, content):
    return {
        "type": "user",
        "uuid": node,
        "parentUuid": parent,
        "timestamp": "2026-01-01T00:00:01Z",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": call,
                    "is_error": is_error,
                    "content": content,
                }
            ],
        },
    }


class ContentMinimizedAnalysisArmsTest(unittest.TestCase):
    def test_content_and_identifiers_never_serialize(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = root / "-home-me" / "native-private-name.jsonl"
            records = [
                {
                    "type": "user",
                    "uuid": "SECRET-NATIVE-USER-NODE",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "SECRET PROMPT WITH CUSTOMER NAME",
                            }
                        ],
                    },
                },
                tool_use(
                    "SECRET-NATIVE-CALL-NODE",
                    "SECRET-NATIVE-USER-NODE",
                    "SECRET-CALL-ONE",
                    "Bash",
                ),
                tool_result(
                    "SECRET-NATIVE-ERROR-NODE",
                    "SECRET-NATIVE-CALL-NODE",
                    "SECRET-CALL-ONE",
                    True,
                    "SECRET ERROR OUTPUT",
                ),
                tool_use(
                    "SECRET-NATIVE-RETRY-NODE",
                    "SECRET-NATIVE-ERROR-NODE",
                    "SECRET-CALL-TWO",
                    "Bash",
                ),
                tool_result(
                    "SECRET-NATIVE-SUCCESS-NODE",
                    "SECRET-NATIVE-RETRY-NODE",
                    "SECRET-CALL-TWO",
                    False,
                    "SECRET SUCCESS OUTPUT",
                ),
            ]
            write_jsonl(session, records, malformed=True)
            result = MODULE.analyze_corpus(
                root,
                {
                    "dataset_id": "public/test-corpus",
                    "dataset_revision": "pinned-public-revision",
                    "license": "test",
                },
            )
            serialized = json.dumps(result)

            self.assertNotIn("SECRET", serialized)
            self.assertNotIn("native-private-name", serialized)
            self.assertNotIn("2026-01-01T", serialized)
            self.assertNotIn("/home", serialized.lower())
            self.assertEqual(1, result["S0_metadata"]["malformed_records"])
            self.assertEqual(
                1,
                result["S4_temporal_episode_candidates"][
                    "candidate_tiers"
                ]["high"],
            )

    def test_recovery_tiers_exclude_parallel_success(self):
        evidence = MODULE.SessionEvidence(stratum="test")
        evidence.calls = {
            "error": MODULE.ToolCall(order=100, family="shell"),
            "parallel": MODULE.ToolCall(order=110, family="file_read"),
            "retry": MODULE.ToolCall(order=401, family="shell"),
            "fallback": MODULE.ToolCall(order=3001, family="file_mutation"),
        }
        evidence.results = [
            MODULE.ToolResult(
                order=200, call_reference="error", is_error=True
            ),
            MODULE.ToolResult(
                order=300, call_reference="parallel", is_error=False
            ),
            MODULE.ToolResult(
                order=500, call_reference="retry", is_error=False
            ),
            MODULE.ToolResult(
                order=3100, call_reference="fallback", is_error=False
            ),
        ]

        episodes, ambiguous = MODULE.reconstruct_recoveries(evidence)

        self.assertEqual(1, len(episodes))
        self.assertEqual("high", episodes[0].tier)
        self.assertEqual(1, ambiguous)

    def test_candidate_records_abstain_from_unsupported_claims(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(2):
                records = [
                    tool_use(
                        f"node-{index}-one",
                        f"root-{index}",
                        f"call-{index}-one",
                        "Edit",
                    ),
                    tool_result(
                        f"node-{index}-two",
                        f"node-{index}-one",
                        f"call-{index}-one",
                        True,
                        "private error",
                    ),
                    tool_use(
                        f"node-{index}-three",
                        f"node-{index}-two",
                        f"call-{index}-two",
                        "Write",
                    ),
                    tool_result(
                        f"node-{index}-four",
                        f"node-{index}-three",
                        f"call-{index}-two",
                        False,
                        "private success",
                    ),
                ]
                write_jsonl(
                    root / "-home-me" / f"session-{index}.jsonl",
                    records,
                )

            result = MODULE.analyze_corpus(root, {})
            proposals = result["S6_proposal_records"]["candidate_records"]

            self.assertEqual(1, proposals["memory_review_motifs"])
            self.assertEqual(2, proposals["procedure_review_episodes"])
            self.assertEqual(0, proposals["skill_gap_recommendations"])
            self.assertEqual(
                0, proposals["cross_user_collaboration_recommendations"]
            )
            self.assertEqual(0, proposals["automatic_memory_or_skill_writes"])

    def test_empty_corpus_is_well_defined(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = MODULE.analyze_corpus(Path(temporary), {})

        self.assertEqual(0, result["S0_metadata"]["sessions"])
        self.assertEqual(
            0, result["review_policy"]["selected_session_budget"]
        )
        self.assertIsNone(result["S0_metadata"]["linked_result_share"])
        self.assertEqual(
            1.0,
            result["arm_overlap"]["eligible"]["S1_vs_S2"]["jaccard"],
        )


if __name__ == "__main__":
    unittest.main()
