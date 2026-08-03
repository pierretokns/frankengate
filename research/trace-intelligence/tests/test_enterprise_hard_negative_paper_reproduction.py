import numpy as np

from enterprise_hard_negative_paper_reproduction import (
    PAPER_EMBEDDING_MODELS,
    PAPER_EMBEDDING_REVISIONS,
    bounded_pages,
    encode,
    false_negative_audit,
    select_hard_negative,
)


def test_paper_encoder_manifest_has_six_distinct_models():
    assert len(PAPER_EMBEDDING_MODELS) == 6
    assert len(set(PAPER_EMBEDDING_MODELS)) == 6
    assert set(PAPER_EMBEDDING_MODELS) == set(PAPER_EMBEDDING_REVISIONS)
    assert all(len(revision) == 40 for revision in PAPER_EMBEDDING_REVISIONS.values())


def test_published_inequalities_select_close_but_positive_dissimilar_candidate():
    query = np.asarray([1.0, 0.0])
    positive = np.asarray([0.8, 0.6])
    candidates = np.asarray([
        [0.99, 0.01],  # close to query and far from positive: valid hard negative
        [0.79, 0.61],  # near duplicate of positive: rejected by Eq. 6
        [0.0, 1.0],    # not close enough to query: rejected by Eq. 5
    ])
    assert select_hard_negative(query, positive, candidates, ["hard", "duplicate", "irrelevant"]) == "hard"


def test_bounded_pages_keeps_required_positive_ids():
    pages = [{"page_id": str(index), "text": f"page {index}"} for index in range(20)]
    selected = bounded_pages(pages, {"3", "11"}, 5, seed=7)
    assert {"3", "11"}.issubset({str(page["page_id"]) for page in selected})
    assert len(selected) == 5


def test_jina_style_task_adapters_use_retrieval_roles():
    class Transformer:
        _lora_adaptations = ["retrieval.query", "retrieval.passage"]

    class Model:
        _modules = {"transformer": Transformer()}
        max_seq_length = 512

        def encode(self, texts, *, task, batch_size, normalize_embeddings, show_progress_bar):
            assert task == "retrieval.passage"
            assert batch_size == 2
            assert normalize_embeddings is True
            assert show_progress_bar is False
            return np.ones((len(texts), 3), dtype=np.float32)

    values = encode(Model(), ["document"], "document", 2, 128)
    assert values.shape == (1, 3)


def test_false_negative_audit_marks_secondary_gold_pages_without_calling_unmarked_pages_true_negatives():
    questions = [
        {"question": "q", "gold_page_ids": ["positive", "also-relevant"]},
    ]
    receipt = false_negative_audit(
        [("q", "positive", "also-relevant"), ("q", "positive", "unmarked")],
        questions,
    )
    assert receipt["selected_triplets"] == 2
    assert receipt["annotated_false_negatives"] == 1
    assert receipt["annotated_false_negative_rate"] == 0.5
    assert "requires adjudication" in receipt["interpretation"]
