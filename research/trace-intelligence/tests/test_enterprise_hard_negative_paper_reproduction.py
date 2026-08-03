import numpy as np

from enterprise_hard_negative_paper_reproduction import (
    PAPER_EMBEDDING_MODELS,
    bounded_pages,
    select_hard_negative,
)


def test_paper_encoder_manifest_has_six_distinct_models():
    assert len(PAPER_EMBEDDING_MODELS) == 6
    assert len(set(PAPER_EMBEDDING_MODELS)) == 6


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
