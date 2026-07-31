# FinanceBench embedding-choice benchmark (bounded)

Pinned `FinanceMTEB/FinanceBench` revision `4738010357e3dda4b337abbde86d5b36c3118c8f`: 189 corpus documents, 150 evaluated queries, and 189 qrels.

This is a relevance-only comparison. It does not prove RLS, deletion, Aurora scale, or enterprise transfer.

| arm | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 |
| --- | ---: | ---: | ---: | ---: | ---: |
| tfidf_unigram_bigram | 0.2922 | 0.1667 | 0.4333 | 0.5800 | 0.6867 |
| BalyasnyAI/multilingual-e5-base | 0.8106 | 0.7000 | 0.9600 | 1.0000 | 1.0000 |

The promotion gate remains closed until the winning model is replayed with governed candidate filtering, deletion closure, hard-negative labels, and held-out transfer.
