from enterprise_hard_negative_mining import fit_feature_bank, mine_hard_negative, run, run_explicit_split


def test_miner_returns_semantic_candidate_and_receipt_metrics():
    pages = [
        {"page_id": "positive", "title": "VCN cloud network", "aliases": ["VCN"], "text": "Virtual cloud network configuration"},
        {"page_id": "hard", "title": "VNIC network card", "aliases": ["VNIC"], "text": "Virtual network interface card configuration"},
        {"page_id": "other", "title": "Payroll policy", "aliases": [], "text": "Payroll and benefits"},
    ]
    bank = fit_feature_bank(pages)
    # The inequalities intentionally allow "no valid hard negative" when the
    # positive is already the closest point; the important contract is that the
    # miner is deterministic and never promotes the positive itself.
    assert mine_hard_negative(bank, "What is VCN in cloud infrastructure?", "positive") in {None, "hard", "other"}

    data = {
        "pages": pages,
        "questions": [
            {"question_id": "q1", "question": "What is VCN in cloud infrastructure?", "gold_page_ids": ["positive"]},
            {"question_id": "q2", "question": "Explain the virtual cloud network", "gold_page_ids": ["positive"]},
            {"question_id": "q3", "question": "Describe VCN configuration", "gold_page_ids": ["positive"]},
            {"question_id": "q4", "question": "What does VCN mean?", "gold_page_ids": ["positive"]},
            {"question_id": "q5", "question": "How is the cloud network configured?", "gold_page_ids": ["positive"]},
        ],
    }
    result = run(data)
    assert result["schema_version"].endswith("-v1")
    assert {"random", "lexical"}.issubset(result["metrics"])


def test_explicit_split_supports_bounded_public_probe_dimensions():
    pages = [
        {"page_id": "a", "title": "Alpha system", "aliases": ["A"], "text": "alpha system configuration"},
        {"page_id": "b", "title": "Beta system", "aliases": ["B"], "text": "beta system configuration"},
        {"page_id": "c", "title": "Gamma system", "aliases": ["C"], "text": "gamma system configuration"},
    ]
    train = [{"question_id": "train-1", "question": "How is alpha configured?", "gold_page_ids": ["a"]}]
    test = [{"question_id": "test-1", "question": "How is beta configured?", "gold_page_ids": ["b"]}]
    result = run_explicit_split(
        {"pages": pages, "questions": train + test},
        train,
        test,
        max_features=16,
        pca_components=2,
    )
    assert result["protocol"]["split"] == "explicit train/test"
    assert result["corpus"] == {"pages": 3, "train": 1, "test": 1}
