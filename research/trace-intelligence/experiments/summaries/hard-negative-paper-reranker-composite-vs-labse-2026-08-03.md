# Composite versus LaBSE reranker result

Using the same 500-page/100-train/100-test fixture and the same
`cross-encoder/ms-marco-MiniLM-L-6-v2` triplet reranker, the six-model
composite reached MRR@3 = 0.6767 and MRR@10 = 0.6950 after one epoch. LaBSE
alone reached MRR@3 = 0.6733 and MRR@10 = 0.6936.

When both arms are capped at the same 23 triplets, the composite reaches
MRR@10 = 0.6950 and LaBSE reaches 0.6929, a difference of 0.0021. This remains
statistically uninformative after one seed and one epoch, but it rules out the
simple explanation that LaBSE's apparent parity came only from having more
training examples. The current evidence still does **not** justify paying the
six-encoder inference cost. It justifies a three-seed experiment with random
and lexical controls and reviewed false-negative labels.
