from __future__ import annotations

import math
import unittest

import e2_authorized_retrieval_factorial as e2


def document(
    trace_id: str,
    task: str,
    text: str,
    *,
    repository: str = "repo",
    category: str = "software",
    tags: tuple[str, ...] = ("coding",),
    features: frozenset[str] = frozenset(),
) -> e2.RetrievalDocument:
    return e2.RetrievalDocument(
        trace_id=trace_id,
        task_identity=task,
        repository_family=repository,
        source_family="fixture",
        category=category,
        tags=tags,
        agent="fixture-agent",
        model="fixture-model",
        text=text,
        tokens=e2.normalize_tokens(text),
        identifiers=e2.extract_identifiers(text),
        structured_features=features,
    )


class E2AuthorizedRetrievalFactorialTest(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = [
            document(
                "a1",
                "task-a",
                "pytest src/cache_policy.py AuthorizationEpoch failed",
                features=frozenset({"tool:test", "error:test", "extension:.py"}),
            ),
            document(
                "a2",
                "task-a",
                "inspect src/cache_policy.py then run pytest AuthorizationEpoch",
                features=frozenset({"tool:test", "tool:inspect", "extension:.py"}),
            ),
            document(
                "b1",
                "task-b",
                "pytest src/cache_policy.py but repair unrelated serialization",
                features=frozenset({"tool:test", "extension:.py"}),
            ),
            document(
                "c1",
                "task-c",
                "compile rust router and run cargo test",
                repository="another-repo",
                tags=("rust",),
                features=frozenset({"tool:test", "error:build", "extension:.rs"}),
            ),
        ]

    def test_gold_task_identity_is_not_in_feature_projection(self) -> None:
        left = self.documents[0]
        changed = document(
            left.trace_id,
            "entirely-different-gold-label",
            left.text,
            repository=left.repository_family,
            category=left.category,
            tags=left.tags,
            features=left.structured_features,
        )
        self.assertEqual(left.tokens, changed.tokens)
        self.assertEqual(left.identifiers, changed.identifiers)
        self.assertEqual(left.structured_features, changed.structured_features)

    def test_factorial_builds_four_offline_arms_without_dense(self) -> None:
        arms, channels = e2.build_rankings(self.documents, dense_vectors=None)
        self.assertEqual(
            set(arms),
            {"S0L0D0", "S0L1D0", "S1L0D0", "S1L1D0"},
        )
        self.assertEqual(
            set(channels[0]),
            {"exact", "lexical", "structured"},
        )
        for ranking in arms.values():
            self.assertNotIn(0, ranking[0])

    def test_factorial_builds_all_eight_arms_with_dense(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is optional for the dense runtime")
        vectors = np.asarray(
            [
                [1.0, 0.0],
                [0.99, 0.01],
                [0.2, 0.8],
                [0.0, 1.0],
            ],
            dtype=float,
        )
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        arms, channels = e2.build_rankings(
            self.documents,
            (vectors, vectors),
        )
        self.assertEqual(len(arms), 8)
        self.assertIn("dense", channels[0])
        self.assertEqual(arms["S0L0D1"][0][0], 1)

    def test_dense_channel_uses_separate_query_and_document_vectors(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is optional for the dense runtime")
        query_vectors = np.asarray(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [0.0, 1.0],
                [0.0, 1.0],
            ],
            dtype=float,
        )
        document_vectors = np.asarray(
            [
                [0.0, 1.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [0.0, 1.0],
            ],
            dtype=float,
        )
        arms, channels = e2.build_rankings(
            self.documents,
            (query_vectors, document_vectors),
        )
        self.assertEqual(channels[0]["dense"][0], 1)
        self.assertEqual(arms["S0L0D1"][0][0], 1)

    def test_relevance_metrics_distinguish_hard_negative(self) -> None:
        metrics = e2.relevance_metrics(
            self.documents,
            0,
            [2, 1, 3],
        )
        self.assertEqual(metrics["recall_at_1"], 0.0)
        self.assertEqual(metrics["recall_at_5"], 1.0)
        self.assertEqual(metrics["hard_negative_top1"], 1.0)
        self.assertEqual(metrics["hard_negative_above_first_positive"], 1.0)
        self.assertFalse(math.isnan(metrics["exact_id_recall_at_20"]))

    def test_rrf_is_deterministic(self) -> None:
        rankings = [[3, 2, 1], [2, 3, 1]]
        self.assertEqual(
            e2.reciprocal_rank_fusion(rankings),
            e2.reciprocal_rank_fusion(rankings),
        )
        self.assertEqual(set(e2.reciprocal_rank_fusion(rankings)), {1, 2, 3})

    def test_hard_negative_excludes_same_task(self) -> None:
        self.assertFalse(e2.hard_negative(self.documents[0], self.documents[1]))
        self.assertTrue(e2.hard_negative(self.documents[0], self.documents[2]))
        self.assertFalse(e2.hard_negative(self.documents[0], self.documents[3]))


if __name__ == "__main__":
    unittest.main()
