# Larger diversity extension smoke

On a 500-page, 100-train/100-test TechQA transfer fixture, the published
inequality selector accepted 23% of queries for the six-encoder composite.
LaBSE alone accepted 56%; Qwen3-Embedding-0.6B 23%; BGE-M3 27%; Nomic Embed
v2-MoE 26%; and Arctic Embed-L 26%.

This is the first result that materially changes the research direction: the
older multilingual LaBSE geometry is much less conservative under the paper's
selector than the newer candidates and the six-model composite. That could be
useful for generating more candidate triplets, but it could also mean more
false negatives. We cannot decide between those explanations without reviewed
relevance labels and a fixed reranker comparison.

The result also shows why “newest model wins” and “more diverse models wins”
are both unsafe assumptions for hard-negative mining. The next experiment is a
three-seed, fixed-reranker factorial with random, lexical, each single model,
the six-model composite, and audited enterprise collision slices.
