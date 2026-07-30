import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wisp_recovery_model_adjudication as adjudication  # noqa: E402


LABELS = {
    "relation": ["same_task_retry", "unrelated", "insufficient_evidence"],
    "outcome": ["recovered_verified", "not_recovered", "insufficient_evidence"],
}


def candidate(blind_id: str, family: str) -> dict:
    return {
        "blind_id": blind_id,
        "controlled_tool_family": family,
        "context": [
            {
                "evidence_ref": f"{blind_id}-E1",
                "kind": "tool_call",
                "role": "assistant",
                "candidate_role": "earlier",
                "payload": {"name": "Inspect", "arguments": {"target": "service"}},
            },
            {
                "evidence_ref": f"{blind_id}-E2",
                "kind": "tool_result",
                "role": "tool",
                "candidate_role": "later",
                "payload": {"content": "healthy"},
            },
        ],
        "adjudication_template": {
            field: {"label": None, "evidence_refs": []} for field in LABELS
        },
    }


class WispRecoveryModelAdjudicationTest(unittest.TestCase):
    def test_stratified_selection_is_deterministic_and_exact(self):
        candidates = [
            candidate(f"C-{index:02d}", family)
            for index, family in enumerate(
                ["shell"] * 8 + ["file_change"] * 7 + ["file_read"] * 2
            )
        ]
        quota = {"shell": 3, "file_change": 2, "file_read": 2}

        first = adjudication.select_stratified(candidates, quota, "seed-v1")
        second = adjudication.select_stratified(
            list(reversed(candidates)), quota, "seed-v1"
        )

        self.assertEqual(
            [item["blind_id"] for item in first],
            [item["blind_id"] for item in second],
        )
        self.assertEqual(
            {"shell": 3, "file_change": 2, "file_read": 2},
            adjudication.count_by_family(first),
        )

    def test_stratified_selection_rejects_an_unmet_quota(self):
        with self.assertRaises(adjudication.AdjudicationError):
            adjudication.select_stratified(
                [candidate("C-1", "shell")],
                {"shell": 2},
                "seed-v1",
            )

    def test_parse_and_validate_requires_every_label_and_local_evidence(self):
        item = candidate("C-1", "shell")
        valid = {
            "relation": {
                "label": "same_task_retry",
                "evidence_refs": ["C-1-E1", "C-1-E2"],
            },
            "outcome": {
                "label": "recovered_verified",
                "evidence_refs": ["C-1-E2"],
            },
        }
        parsed = adjudication.parse_and_validate(
            "```json\n" + json.dumps(valid) + "\n```",
            item,
            LABELS,
        )
        self.assertEqual(valid, parsed)

        missing = dict(valid)
        missing.pop("outcome")
        with self.assertRaises(adjudication.AdjudicationError):
            adjudication.parse_and_validate(json.dumps(missing), item, LABELS)

        invalid_ref = json.loads(json.dumps(valid))
        invalid_ref["outcome"]["evidence_refs"] = ["C-other-E9"]
        with self.assertRaises(adjudication.AdjudicationError):
            adjudication.parse_and_validate(json.dumps(invalid_ref), item, LABELS)

        too_many = json.loads(json.dumps(valid))
        too_many["relation"]["evidence_refs"] = [
            "C-1-E1",
            "C-1-E2",
            "C-1-E1",
            "C-1-E2",
        ]
        with self.assertRaises(adjudication.AdjudicationError):
            adjudication.parse_and_validate(json.dumps(too_many), item, LABELS)

    def test_insufficient_evidence_may_use_empty_refs_but_other_labels_may_not(self):
        item = candidate("C-1", "shell")
        result = {
            "relation": {
                "label": "insufficient_evidence",
                "evidence_refs": [],
            },
            "outcome": {
                "label": "insufficient_evidence",
                "evidence_refs": [],
            },
        }
        adjudication.parse_and_validate(json.dumps(result), item, LABELS)

        result["relation"]["label"] = "same_task_retry"
        with self.assertRaises(adjudication.AdjudicationError):
            adjudication.parse_and_validate(json.dumps(result), item, LABELS)

    def test_fleiss_kappa_handles_perfect_and_chance_agreement(self):
        perfect = [["a", "a", "a"], ["b", "b", "b"], ["a", "a", "a"]]
        self.assertAlmostEqual(1.0, adjudication.fleiss_kappa(perfect), places=8)

        balanced = [
            ["a", "a", "b"],
            ["a", "b", "b"],
            ["a", "b", "a"],
            ["b", "a", "b"],
        ]
        self.assertLess(adjudication.fleiss_kappa(balanced), 0.1)

    def test_aggregate_exposes_no_candidate_ids_or_labels_by_case(self):
        selected = [candidate("C-1", "shell"), candidate("C-2", "file_change")]
        rows = []
        for pass_id, relation in enumerate(
            ["same_task_retry", "same_task_retry", "unrelated"]
        ):
            for item in selected:
                rows.append(
                    {
                        "blind_id": item["blind_id"],
                        "pass_id": f"p{pass_id}",
                        "status": "valid",
                        "labels": {
                            "relation": {
                                "label": relation,
                                "evidence_refs": [item["context"][0]["evidence_ref"]],
                            },
                            "outcome": {
                                "label": "recovered_verified",
                                "evidence_refs": [item["context"][1]["evidence_ref"]],
                            },
                        },
                    }
                )

        result = adjudication.aggregate(
            selected=selected,
            rows=rows,
            label_contract=LABELS,
            pass_ids=["p0", "p1", "p2"],
        )

        encoded = json.dumps(result)
        self.assertNotIn("C-1", encoded)
        self.assertNotIn("C-2", encoded)
        self.assertEqual(2, result["sample"]["candidate_count"])
        self.assertEqual(1.0, result["agreement"]["outcome"]["unanimous_fraction"])
        self.assertEqual(0.0, result["execution"]["errored_fraction"])

    def test_write_raw_jsonl_uses_restrictive_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "raw.jsonl"
            adjudication.write_raw_jsonl(
                path,
                [{"blind_id": "C-1", "status": "valid"}],
            )
            self.assertEqual(0o600, path.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
