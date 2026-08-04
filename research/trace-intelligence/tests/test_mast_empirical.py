import importlib.util
import pathlib
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "mast_empirical.py"
SPEC = importlib.util.spec_from_file_location("mast_empirical", MODULE_PATH)
mast = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mast)


class MastAdapterTest(unittest.TestCase):
    def canonical(self, text, framework):
        return mast.canonicalize_mast_trace(
            text,
            framework=framework,
            benchmark="fixture",
            source_trace_key="fixture-key",
        )

    def test_source_lines_round_trip_without_silent_drop(self):
        source = "first line\n\nlast line without newline"
        canonical = self.canonical(source, "Unknown")
        self.assertEqual(
            source, "".join(event["content"] for event in canonical["events"])
        )
        receipt = canonical["loss_receipt"]
        self.assertEqual(3, receipt["source_event_count"])
        self.assertEqual(3, receipt["canonical_event_count"])
        self.assertEqual(0, receipt["silently_dropped_event_count"])
        self.assertTrue(receipt["source_text_round_trip"])

    def test_metagpt_explicit_edge_preserves_both_endpoints(self):
        source = (
            "[2025-01-01 00:00:00] FROM: Human TO: {'<all>'}\n"
            "CONTENT:\nhello\n"
        )
        canonical = self.canonical(source, "MetaGPT")
        edge = canonical["communications"][0]
        self.assertEqual("Human", edge["sender"])
        self.assertEqual("{'<all>'}", edge["receiver"])
        self.assertEqual("observed", edge["observation_status"])
        self.assertTrue(edge["complete_endpoints"])

    def test_metagpt_message_actor_is_preserved_as_role(self):
        canonical = self.canonical(
            "[time] FROM: Human TO: {'<all>'}\n"
            "NEW MESSAGES:\n"
            "SimpleCoder:\n"
            "implementation\n",
            "MetaGPT",
        )
        self.assertIn("Human", canonical["agent_roles"])
        self.assertIn("SimpleCoder", canonical["agent_roles"])
        reconstructed = [
            edge
            for edge in canonical["communications"]
            if edge["observation_status"] == "reconstructed"
        ]
        self.assertEqual("Human", reconstructed[0]["sender"])
        self.assertEqual("SimpleCoder", reconstructed[0]["receiver"])

    def test_chatdev_turn_uses_log_speaker_to_direct_edge(self):
        source = (
            "[2025-31-03 19:10:00 INFO] Chief Technology Officer: "
            "**Chief Technology Officer<->Chief Executive Officer on : "
            "LanguageChoose, turn 0**\n"
        )
        canonical = self.canonical(source, "ChatDev")
        edge = canonical["communications"][0]
        self.assertEqual("Chief Technology Officer", edge["sender"])
        self.assertEqual("Chief Executive Officer", edge["receiver"])
        self.assertEqual("LanguageChoose", edge["phase"])
        self.assertEqual("observed", edge["observation_status"])

    def test_appworld_partial_edge_is_not_completed_by_inference(self):
        canonical = self.canonical(
            "Message to spotify Agent\nResponse from spotify Agent\n",
            "AppWorld",
        )
        observed = [
            edge
            for edge in canonical["communications"]
            if edge["observation_status"] == "observed"
        ]
        self.assertEqual(2, len(observed))
        self.assertTrue(all(not edge["complete_endpoints"] for edge in observed))
        self.assertIsNone(observed[0]["sender"])
        self.assertIsNone(observed[1]["receiver"])

    def test_magentic_adjacency_is_reconstructed_not_observed_handoff(self):
        canonical = self.canonical(
            "---------- MagenticOneOrchestrator ----------\n"
            "do work\n"
            "---------- WebSurfer ----------\n"
            "result\n",
            "Magentic",
        )
        reconstructed = [
            edge
            for edge in canonical["communications"]
            if edge["observation_status"] == "reconstructed"
        ]
        self.assertEqual(1, len(reconstructed))
        self.assertEqual("MagenticOneOrchestrator", reconstructed[0]["sender"])
        self.assertEqual("WebSurfer", reconstructed[0]["receiver"])

    def test_framework_specific_markers_do_not_cross_parse(self):
        canonical = self.canonical(
            "[time] FROM: Human TO: {'<all>'}\n"
            "Message to spotify Agent\n",
            "OpenManus",
        )
        self.assertEqual([], canonical["communications"])
        self.assertEqual([], canonical["agent_roles"])

    def test_labels_are_not_inserted_into_canonical_trace(self):
        canonical = self.canonical("plain trace\n", "MetaGPT")
        self.assertNotIn("mast_annotation", canonical)
        self.assertIsNone(canonical["outcome"]["value"])


class MastAnnotationTest(unittest.TestCase):
    def judge_row(self, positives=()):
        return {
            "mas_name": "MetaGPT",
            "llm_name": "GPT-4o",
            "benchmark_name": "ProgramDev",
            "trace_id": 1,
            "trace": {"key": "k", "index": 0, "trajectory": "trace\n"},
            "mast_annotation": {
                code: int(code in positives) for code in mast.MAST_CODES
            },
        }

    def human_row(self, finalized=True):
        modes = (
            list(mast.MAST_TAXONOMY.items())
            if finalized
            else [("1.1", "Old meaning"), ("1.2", "Another old meaning")]
        )
        return {
            "round": "Generlazability" if finalized else "Round 1",
            "mas_name": "Fixture",
            "benchmark_name": "Fixture",
            "trace_id": 1,
            "trace": "human trace\n",
            "annotations": [
                {
                    "failure mode": f"{code} {title}\n\nDefinition",
                    "annotator_1": code == "1.1",
                    "annotator_2": code == "1.1",
                    "annotator_3": False,
                }
                for code, title in modes
            ],
        }

    def test_judge_schema_requires_exact_ordered_14_codes(self):
        labels = mast._validate_judge_labels(self.judge_row(("1.1",)))
        self.assertEqual(1, labels["1.1"])
        broken = self.judge_row()
        broken["mast_annotation"] = dict(reversed(broken["mast_annotation"].items()))
        with self.assertRaises(ValueError):
            mast._validate_judge_labels(broken)

    def test_human_finalized_and_development_taxonomies_stay_separate(self):
        result = mast._human_study(
            [self.human_row(finalized=True), self.human_row(finalized=False)]
        )
        self.assertEqual(1, result["finalized_14_mode_partition"]["n"])
        self.assertEqual(1, result["taxonomy_development_partition"]["n"])
        self.assertEqual(
            "not_aggregated_across_incompatible_taxonomies",
            result["taxonomy_development_partition"]["aggregation_status"],
        )
        self.assertEqual(
            1,
            result["finalized_14_mode_partition"][
                "majority_positive_trace_counts"
            ]["1.1"],
        )

    def test_prediction_metrics_are_multilabel_and_deterministic(self):
        labels = [
            {code: int(code == "1.1") for code in mast.MAST_CODES},
            {code: 0 for code in mast.MAST_CODES},
        ]
        predictions = [{code: 0 for code in mast.MAST_CODES} for _ in labels]
        metrics = mast._prediction_metrics(labels, predictions)
        self.assertEqual(0.5, metrics["exact_match_accuracy"])
        self.assertEqual(0.0, metrics["micro_recall"])
        self.assertEqual(0.0, metrics["micro_f1"])
        self.assertAlmostEqual(
            (2 * len(mast.MAST_CODES) - 1) / (2 * len(mast.MAST_CODES)),
            metrics["hamming_accuracy"],
        )

    def test_no_finalized_overlap_blocks_human_judge_scoring(self):
        full = [self.judge_row()]
        human = [self.human_row(finalized=True)]
        overlap = mast._overlap_study(full, human)
        self.assertEqual(
            0,
            overlap["exact_trace_sha256_overlap"]["finalized_human_vs_judge"],
        )
        self.assertEqual(
            "not_run_no_finalized_taxonomy_trace_overlap",
            overlap["human_vs_judge_scoring_status"],
        )

    def test_analyze_release_keeps_authorities_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            full_path = root / "MAD_full_dataset.json"
            human_path = root / "MAD_human_labelled_dataset.json"
            full_rows = []
            for index in range(50):
                row = self.judge_row(("1.1",) if index % 2 else ())
                row["trace_id"] = index
                row["trace"] = {
                    "key": f"k-{index}",
                    "index": index,
                    "trajectory": f"trace {index}\n",
                }
                full_rows.append(row)
            full_path.write_text(
                mast.json.dumps(full_rows), encoding="utf-8"
            )
            human_path.write_text(
                mast.json.dumps([self.human_row(finalized=True)]),
                encoding="utf-8",
            )
            result = mast.analyze_release(full_path, human_path)
        self.assertTrue(
            result["study_design"]["annotation_authorities_never_merged"]
        )
        self.assertFalse(
            result["naive_baselines"]["human_labels_used_for_fitting_or_scoring"]
        )
        self.assertFalse(
            result["study_design"]["single_agent_or_enterprise_transfer_claim"]
        )


if __name__ == "__main__":
    unittest.main()
