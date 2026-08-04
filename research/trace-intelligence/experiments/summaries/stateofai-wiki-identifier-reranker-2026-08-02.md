# State of AI wiki identifier reranker — 2026-08-02

## Protocol

This is a narrow follow-up to the real State of AI wiki-export run. The
adapter produced 1,281 pages across 25 source-domain partitions and 301
identity queries. BGE-base produced the top 20 candidates; a transparent
reranker then added token overlap and an exact source-ID feature. The labels
are source-record identity labels, not human answer or task-success labels.

## Results

| domains | R@1 | R@20 | MRR | NIL false-positive rate |
|---:|---:|---:|---:|---:|
| 1 | .917 | 1.000 | .933 | 1.000 |
| 5 | .900 | 1.000 | .933 | 1.000 |
| 10 | .875 | .992 | .919 | 1.000 |
| 25 | .777 | .920 | .812 | 1.000 |

At 25 domains this transparent reranker improves over the previously measured
raw BGE R@1 (.520) and compiled BGE R@1 (.573), but remains below compiled FTS
R@1 (.947). It does not solve abstention: the generated NIL query still gets
a candidate at every scale.

## Interpretation

The result supports a small, auditable retrieval cascade: preserve exact
identifiers and metadata, use lexical/structured filtering for identity, then
use semantic candidates and a reranker for paraphrase or missing identifiers.
It does not justify training a custom embedding model yet. The reranker is
hand-weighted and evaluated on silver identity queries; reviewed paraphrases,
aliases, adversarial same-domain negatives, and multiple NILs are required
before claiming enterprise retrieval gains.

## Claim boundary

This is not a Claude Code/Codex answer-quality benchmark, not native MCP
evidence, and not proof of a production wiki architecture. The real corpus is
valuable for metadata and hard-negative construction, but it is not a set of
independent enterprise wikis.

Receipt: [content-minimized result](../results/stateofai-wiki-identifier-reranker-2026-08-02.json)
