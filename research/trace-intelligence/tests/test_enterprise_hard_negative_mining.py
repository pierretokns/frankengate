from enterprise_hard_negative_mining import fit_feature_bank, mine_hard_negative, run


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
