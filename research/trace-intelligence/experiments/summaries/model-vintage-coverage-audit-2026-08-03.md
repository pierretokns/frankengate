# Model-vintage coverage audit

The Oracle hard-negative reproduction now has an explicit model-vintage
companion. This audit records which adjacent reproduction tracks already have
model comparisons and which still need them. It prevents a strong result from
one corpus from being silently generalized to every trace-learning method.

## Coverage by reproduction or evidence track

| Track | Older/control arm | Newer/current arm | Evidence status | Next action |
|---|---|---|---|---|
| Oracle enterprise hard-negative transfer | TF-IDF surrogate and `all-MiniLM-L6-v2` | Arctic Embed-S and Qwen3-Embedding-0.6B | **Measured** on bounded TechQA; Qwen3 was strongest on MRR@10 (`.8540`) | Repeat on FiQA and then on family-disjoint reviewed enterprise hard negatives |
| MATM cross-model trace retrieval | lexical goal/action similarity | Nomic action/goal embeddings; fold-local adapter | **Measured**, but Nomic is the only dense checkpoint and the adapter is neutral on the silver task | Keep model-vintage comparison in shadow; do not infer skill utility |
| WMH-BIRD SQL table retrieval | lexical and Nomic dense | frontier review plus a fold-local Nomic adapter | **Measured**, but model review changes shortlist precision rather than target recall; adapter trades Recall@5 for a small Recall@1 gain | Test newer dense checkpoints only on the same reviewed, collision-heavy cohort |
| FinanceBench retrieval | loopback Nomic and Qwen3 | E5 family | **Measured** with serving identity and latency; E5 was strongest in the recorded receipt | Preserve model snapshot/prefix/endpoint as index identity |
| EnterpriseRAG-Bench document retrieval | lexical and MiniLM | frontier reranking | **Measured** as a public document proxy; newer dense checkpoint not yet compared | Add one current open checkpoint under the identical full-corpus protocol before architecture decisions |
| Term/alias extraction | legacy Termolator/AcronymExpansion | GLiNER/current ports and frontier review | **Partially measured**; this is a model-family modernization question, not an embedding result | Compare candidate recall, NIL/temporal collisions, and reviewed retrieval lift |
| SkillGen/SkillOpt/ReasoningBank | paper-era mechanics and controls | frontier/local harness variants | **Not an embedding-vintage question**; the missing evidence is changed-system task efficacy | Do not substitute a new encoder for the required randomized skill arms |

## Interpretation

The model-vintage result is useful where the method's claim includes semantic
candidate generation. It is not a universal upgrade rule. A newer encoder can
raise retrieval recall while still worsening identifier collisions, latency,
cost, or downstream artifact validity. Every comparison therefore keeps the
same candidate pool, split, labels, reranker budget, replay gate, and serving
identity.

The strongest current pattern is:

```text
scope + authority + exact identifiers
  -> lexical/structured retrieval
  -> model-vintage dense expansion (shadow lane)
  -> selective frontier or human review
  -> independent replay and changed-system validation
```

The model-vintage track does not authorize a universal corporate embedding or
replace the P0 consented cohort. It closes one reproducibility hygiene gap:
paper-era controls and current open checkpoints are now compared rather than
assuming that an older baseline represents the current frontier.

Receipts:

- [`hard-negative-public-model-vintage-techqa-2026-08-03.json`](../results/hard-negative-public-model-vintage-techqa-2026-08-03.json)
- [`matm-embedding-similarity-benchmark-2026-08-02.json`](../results/matm-embedding-similarity-benchmark-2026-08-02.json)
- [`wmh-bird-sql-dense-frontier-cohort-2026-08-09.json`](../results/wmh-bird-sql-dense-frontier-cohort-2026-08-09.json)
- [`finance-embedding-cross-receipt-audit-2026-08-02.json`](../results/finance-embedding-cross-receipt-audit-2026-08-02.json)
- [`enterprise-rag-dense-baseline-2026-08-02.json`](../results/enterprise-rag-dense-baseline-2026-08-02.json)
