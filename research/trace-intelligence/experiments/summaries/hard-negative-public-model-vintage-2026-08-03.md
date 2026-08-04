# Hard-negative reproduction: model-vintage transfer probe

This is the model-vintage companion to the clean-room reproduction of Oracle's
ACL 2025 paper, [Hard Negative Mining for Domain-Specific Retrieval in
Enterprise Systems](https://arxiv.org/abs/2505.18366). The paper's private
six-bi-encoder ensemble and triplet-trained reranker are not public, so the
comparison keeps the public transfer data and retrieval protocol explicit
instead of claiming a literal reproduction.

## Parallel model arms

NTM pane 6 ran the same deterministic TechQA-RAG-Eval candidate pool through a
paper-era CPU lexical surrogate, the older dense `all-MiniLM-L6-v2` baseline,
and two newer open checkpoints. No raw question, answer, context, or document
text was committed; the candidate and qrels hashes are in the receipt.

| arm | MRR@10 | NDCG@10 | Recall@10 | Recall@20 |
|---|---:|---:|---:|---:|
| TF-IDF word 1–2 gram surrogate | 0.7088 | 0.7524 | 0.8854 | 0.9375 |
| `sentence-transformers/all-MiniLM-L6-v2` | 0.7643 | 0.7940 | 0.8854 | 0.9479 |
| `Snowflake/snowflake-arctic-embed-s` | 0.8163 | 0.8402 | 0.9167 | 0.9479 |
| `Qwen/Qwen3-Embedding-0.6B` | **0.8540** | **0.8771** | **0.9479** | **0.9583** |

On this bounded slice, the newer checkpoints improved MRR@10 over the older
dense baseline by 0.0520 (Arctic-Embed-S) and 0.0897 (Qwen3-Embedding-0.6B).
That is useful evidence for keeping model-vintage arms in every reproduction,
but it is not evidence that either model is universally best for enterprise
traces: the corpus is only 1,115 candidate documents and positives are the
explicit TechQA context filenames.

## What this changes in the reproduction plan

1. Every paper reproduction gets a model manifest with the paper-era control,
   the strongest currently available open checkpoint that fits the runtime,
   and at least one intermediate/current alternative.
2. Model changes are evaluated under the same candidate pool, split, seed,
   metric definitions, reranker budget, and false-negative audit. A new model
   cannot be credited for a changed dataset or a changed judge.
3. The Oracle-specific experiment remains open: the public probe does not test
   the six-encoder concatenation, PCA-fit scope, triplet loss, or private
   enterprise corpus. Those are separate reproduction gates.
4. Promotion requires gains on family-disjoint enterprise traces and changed
   system slices, not only a public TechQA transfer number.

Receipt: [`hard-negative-public-model-vintage-techqa-2026-08-03.json`](../results/hard-negative-public-model-vintage-techqa-2026-08-03.json)

The public dataset is [NVIDIA TechQA-RAG-Eval](https://huggingface.co/datasets/nvidia/TechQA-RAG-Eval), licensed Apache-2.0 according to its local README. The older and newer model cards are linked in the receipt for independent verification.
