from __future__ import annotations

import unittest

import e2_authorized_retrieval_factorial as e2
import e2_postgres_joint_retrieval as joint


class E2PostgresJointRetrievalTest(unittest.TestCase):
    def test_fts_query_is_bounded_unique_and_syntax_safe(self) -> None:
        text = " ".join(
            ["alpha", "alpha", "src/cache.py", "AuthorizationEpoch"]
            + [f"Term{index}" for index in range(100)]
        )
        query = joint.fts_query_text(text)
        terms = query.split(" | ")
        self.assertEqual(len(terms), joint.FTS_TERM_LIMIT)
        self.assertEqual(terms[0], "alpha")
        self.assertEqual(len(terms), len(set(terms)))
        self.assertTrue(all(joint.FTS_WORD_RE.fullmatch(term) for term in terms))

    def test_percentiles_use_linear_interpolation(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(joint.percentile(values, 0.50), 2.5)
        self.assertAlmostEqual(joint.percentile(values, 0.95), 3.85)
        summary = joint.latency_summary(values)
        self.assertEqual(summary["samples"], 4)
        self.assertIn("p99_ms", summary)

    def test_ordered_indices_requires_exact_authorized_candidate_set(self) -> None:
        rows = [("b", 1.0), ("c", 0.5)]
        ranking = joint.ordered_indices(
            rows,
            id_to_index={"a": 0, "b": 1, "c": 2},
            query_index=0,
            document_count=3,
        )
        self.assertEqual(ranking, [1, 2])
        with self.assertRaises(ValueError):
            joint.ordered_indices(
                rows[:1],
                id_to_index={"a": 0, "b": 1, "c": 2},
                query_index=0,
                document_count=3,
            )

    def test_vector_literal_requires_native_qwen_dimension(self) -> None:
        with self.assertRaises(ValueError):
            joint.vector_literal([0.0, 1.0])
        literal = joint.vector_literal(
            [0.0] * e2.EXPECTED_EMBEDDING_DIMENSION
        )
        self.assertTrue(literal.startswith("["))
        self.assertTrue(literal.endswith("]"))
        self.assertEqual(literal.count(","), e2.EXPECTED_EMBEDDING_DIMENSION - 1)

    def test_content_free_guard_rejects_source_identity(self) -> None:
        document = e2.RetrievalDocument(
            trace_id="sensitive-trace-identity",
            task_identity="sensitive-task-identity",
            repository_family="fixture",
            source_family="fixture",
            category="",
            tags=(),
            agent="fixture",
            model="fixture",
            text="raw fixture text",
            tokens=("raw", "fixture", "text"),
            identifiers=frozenset(),
            structured_features=frozenset(),
        )
        joint.assert_content_free_result({"aggregate": 1}, [document])
        with self.assertRaises(ValueError):
            joint.assert_content_free_result(
                {"aggregate": document.trace_id},
                [document],
            )


if __name__ == "__main__":
    unittest.main()
