# MATM local embedding similarity benchmark (2026-08-02)

## Protocol

This is a same-corpus cross-model retrieval study over the pinned MATM
ALFWorld shard (2,130 rows, 34 models). Each fold holds out one model and
retrieves from all other models. Because `task_id` is model-local, the valid
relevance label is a repeated `(task_type, normalized goal)` signature; only
33 model folds and 636 query rows have at least one cross-model match. Outcome
is used only to report the success rate of retrieved neighbors, never to rank
the query.

The arms are lexical goal+action, lexical action-only, Ollama
`nomic-embed-text:latest` goal-only, embedding goal+action, and embedding
action-only. The action-only arm hides the goal from the retriever, avoiding
the direct label leak in the goal arm. The loopback embedding endpoint was
`http://127.0.0.1:11434`; raw text and vectors were not committed.

## Results

| arm | Recall@1 | Recall@5 | Recall@10 | Recall@20 | MRR | top-10% successful-neighbor rate |
|---|---:|---:|---:|---:|---:|---:|
| lexical goal+action | 0.995 | 1.000 | 1.000 | 1.000 | 0.997 | 0.399 |
| lexical action-only | 0.237 | 0.320 | 0.368 | 0.407 | 0.283 | 0.343 |
| embedding goal-only | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.419 |
| embedding goal+action | 0.735 | 0.805 | 0.911 | 0.995 | 0.784 | 0.381 |
| embedding action-only | 0.271 | 0.352 | 0.460 | 0.530 | 0.332 | 0.374 |

Across the 33 matched model folds, embedding action-only improved Recall@20
over lexical action-only by `+0.123` (bootstrap 95% CI `[+0.053, +0.206]`) and
MRR by `+0.048` (CI `[-0.002, +0.100]`). The successful-neighbor precision
change was only `+0.031` (CI `[-0.005, +0.068]`). Embedding goal+action was
slightly below the lexical goal+action upper bound (`-0.005` Recall@20,
CI `[-0.015, 0.000]`).

## Interpretation

This is the first direct evidence here that a local semantic embedding can
recover cross-model same-work signatures from action traces when the goal is
hidden: it beats the lexical action baseline on retrieval recall. It does not
show that retrieved traces improve an agent, select better skills, or identify
people. The exact-goal arms are an upper bound with label leakage, and the
cross-model signature cohort is only 33 folds/636 queries. No custom fine-tune,
RLS, deletion, Aurora, or changed-agent replay was run.

Decision: keep a semantic embedding as an optional retrieval candidate for
review queues, but do not promote a custom embedding or use similarity as a
skill-release authority. The next gate is the same action-only/goal-held-out
comparison on independently adjudicated enterprise hard negatives, followed
by a changed-agent replay if retrieval is used to construct a procedure.

Machine receipt: [`matm-embedding-similarity-benchmark-2026-08-02.json`](../results/matm-embedding-similarity-benchmark-2026-08-02.json).
Runner: [`matm_embedding_similarity_benchmark.py`](../../matm_embedding_similarity_benchmark.py).
