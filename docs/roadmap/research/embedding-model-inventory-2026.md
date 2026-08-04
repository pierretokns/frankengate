# Open embedding model inventory (2026)

Status: candidate inventory and evaluation plan. No model is approved for
production or fine-tuning by this document.

## Candidate matrix

| Candidate | Evidence and fit | License/deployment caution | Initial lane |
|---|---|---|---|
| Qwen3-Embedding family | Open model family with configurable output dimensions up to 2,560 for the 4B model; strong general retrieval candidate | Verify the exact model-card license and tokenizer revision for every checkpoint | Baseline dense model; evaluate 0.6B/4B size trade-off |
| Fin-E5 / FinPersona-E5 | Finance-adapted model from FinMTEB work; domain adaptation is directly relevant to filings, news, ESG, and earnings calls | Verify checkpoint provenance, training-data terms, and redistribution notice before embedding sensitive corpora | Finance-specialist challenger |
| BGE/E5 open families | Mature open baselines with broad tooling and reproducible local serving | Benchmark the exact checkpoint and pooling/normalization recipe; model names alone are not a reproducible configuration | Control baselines |
| NVIDIA NeMo Retriever/Nemotron embeddings | Production-style embedding API exposes model metadata, manifests, license, health, metrics, and multimodal inputs | NIM images and some models have separate commercial or model-license terms; do not treat the Apache-licensed source as blanket permission to redistribute weights | Optional managed/self-hosted accelerator lane |
| Small local encoder (MiniLM-class) | Cheap endpoint-local classification and cache/routing features | Domain quality may be inadequate; must pass hard-negative and ACL-aware retrieval tests | Fast classifier/cache-only lane, not default corpus authority |

## Evaluation requirements

FinMTEB contains 64 finance datasets across seven tasks and reports that
domain-adapted models can outperform general-purpose models, while simple BoW
methods can win financial semantic-similarity tasks. Therefore no single
leaderboard score is sufficient. Every candidate must be evaluated on:

- FinMTEB finance cohorts plus the local finance/jargon corpus;
- English and Chinese slices where applicable;
- lexical, dense, hybrid, reranked, and adapted arms;
- hard negatives for tickers, acronyms, legal entities, dates, units, and
  near-duplicate filings;
- ACL/tenant filtering, deletion tombstones, stale policy, and legal-hold cases;
- recall@k, nDCG, MRR, answer-support rate, p50/p95 embedding latency, memory,
  index build time, and cost per million tokens.

## Immutable embedding contract

Pin model ID and revision, tokenizer ID/revision, query/document prompts,
pooling, normalization, dimension, distance metric, chunking policy, and index
revision. A model swap requires a shadow index and frozen holdout; never mutate
weights or vectors in place. Store no plaintext in the Git benchmark manifest.
Instead record governed query/document source references, content disposition,
classification, purpose, policy/authorization/deletion epochs, and hashes. The
authorized runner resolves full text locally under current RLS; credentials are
excluded before either source storage or evaluation.

## Frankengate E2 evidence update

The first trace-specific dense baseline now uses
[`Qwen/Qwen3-Embedding-0.6B`](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
at immutable revision
`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`. The contract fixes separate
instructed query and bare-document embeddings, 1,024 dimensions, L2
normalization, cosine distance, a 512-token experimental cap, and the exact
tokenizer/model configuration hashes.

On the frozen 145-archive CodeTraceBench raw slice, the best
structured-plus-general-dense arm reached Recall@20 `0.8182`, compared with
`0.7323` for exact identifiers alone. The paired bootstrap interval for the
gain was `[0.0354, 0.1364]`. Dense alone reached `0.7374`, with an interval that
included zero. Adding raw-trajectory lexical retrieval could reduce recall and
exact-identifier preservation. These are silver task-identity labels, not
human-adjudicated enterprise relevance.

This result supports three decisions:

1. keep structured JSONB/task views and exact identifiers as first-class
   retrieval inputs;
2. retain a general embedding as a conditional candidate channel, but do not
   train a corporate adapter yet; and
3. do not add another vector database. The next gate is the same frozen
   candidates in forced-RLS PostgreSQL with native FTS/trigram, exact pgvector,
   withdrawal/deletion, selectivity, latency, and human-reviewed hard
   negatives.

## Promotion policy

The default production path remains PostgreSQL/pgvector once its adapter exists.
Frankensearch is an optional derived hybrid index. NVIDIA NIM is an optional
deployment lane, not a licensing shortcut. Promotion requires human MR approval,
license/provenance evidence, ACL/deletion conformance, and a rollback-ready
dual-index manifest.

## Sources

- [FinMTEB paper and dataset](https://arxiv.org/abs/2502.10990)
- [Qwen3-Embedding-4B model card](https://huggingface.co/Qwen/Qwen3-Embedding-4B)
- [NVIDIA NeMo Retriever embedding API](https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/reference.html)
- [NVIDIA NeMo Retriever license guidance](https://docs.nvidia.com/nemo/retriever/latest/license/index.html)
- [NVIDIA NeMo Retriever source](https://github.com/NVIDIA-NeMo/NeMo-Retriever)
