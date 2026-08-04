# Triplet-reranker execution smoke

The paper's second stage now executes end to end: six-model hard-negative
mining produced 6 training triplets, a `cross-encoder/ms-marco-MiniLM-L-6-v2`
reranker trained for one epoch with the margin objective, and the held-out
10-question fixture scored MRR@3 = MRR@10 = 0.8667.

This is a pipeline verification, not a result to optimize against. It lacks a
zero-shot reranker baseline, random/lexical/single-model negative arms,
multiple seeds, and audited relevance labels. The next experiment must compare
those arms under one fixed reranker before we infer that the composite helps.
