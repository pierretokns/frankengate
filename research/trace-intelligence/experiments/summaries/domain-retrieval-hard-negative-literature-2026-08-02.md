# Domain retrieval and hard-negative literature map — 2026-08-02

## Closest adjacent work

| Work | What it actually contributes | Frankengate adaptation | Boundary |
|---|---|---|---|
| [Hard Negative Mining for Domain-Specific Retrieval in Enterprise Systems](https://arxiv.org/abs/2505.18366) | Dynamic semantic-but-irrelevant negatives for enterprise rerankers; reports gains on a cloud-services corpus | Mine negatives from multiple retrievers, then separate lexical overlap, semantic similarity, and contextual irrelevance; train the reranker before the embedding model | Proprietary cloud corpus and reported results are not independently reproduced here |
| [Remining Hard Negatives for GPL](https://arxiv.org/abs/2501.14434) | Refreshes the negative index as the retriever changes during pseudo-label adaptation | Re-mine negatives after every adapter checkpoint instead of freezing BGE candidates | Public BEIR/LoTTE transfer is not corporate trace evidence |
| [BiCA citation-aware negatives](https://arxiv.org/abs/2511.08029) | Uses graph links as naturally related-but-not-identical negatives | Use wiki links, trace parent/child edges, and artifact lineage as negative candidates | Citation graphs are cleaner than enterprise logs |
| [Domain-adaptation with pseudo-relevance labels](https://aclanthology.org/2024.lrec-main.467/) | Generates target-domain queries and meticulous negatives without full human labeling | Use frontier-generated query variants only as silver data, then require human or execution validation for promotion | Pseudo-label quality is the central risk |
| [SCAIR](https://aclanthology.org/2026.acl-industry.76/) | Schema-conditioned traversal for dense, operational enterprise knowledge graphs | Add typed entity/schema gates before semantic retrieval for system, environment, owner, version, and time | CMDB benchmark is more structured than raw traces |
| [MIT Data Civilizer/Aurum](https://www.csail.mit.edu/research/data-discovery) | Enterprise knowledge graph for discovering and relating data assets | Treat traces, SQL artifacts, schemas, aliases, and ownership as discoverable assets, not just text chunks | Older system; must be reimplemented against current tool traces |

## What our measurements add

The quality-filtered State of AI run is consistent with these papers but more
diagnostic for our setting:

- compiled FTS R@1 `.749` at ten domains;
- general BGE R@1 `.456` raw and `.476` compiled;
- a transparent identifier reranker over BGE `.695`;
- NIL false-positive rate `1.0` for every arm;
- automatically mined same-domain distractors entered top-20 about `74%` of the
  time but displaced the gold result at rank 1 only `3–5%` of the time.

This says our next training data should not be “all nearest neighbors.” It
should be a typed mixture:

1. lexical near-matches with different entities;
2. semantic near-matches with different task outcomes;
3. same-system different-version records;
4. linked but non-answer-bearing pages;
5. genuine NILs and abstention cases.

The first category is already measurable. The remaining categories require
trace-derived metadata or adjudication.

## Publication and partnership candidates

- MIT CSAIL Data Systems Group is the strongest systems partner for enterprise
  asset discovery, schema/lineage graphs, and cost-aware retrieval.
- MIT CSAIL/adjacent agent-retrieval researchers are a good fit for the
  tool-call trajectory and frontier-agent evaluation layer.
- Harvard’s [Zitnik Lab](https://zitniklab.hms.harvard.edu/research/) is an
  adjacent graph/knowledge-grounding partner, especially if the study uses
  entity provenance, relation extraction, and evidence verification. It is not
  a direct enterprise-trace match.
- The publishable gap is not “another RAG benchmark.” It is a controlled study
  of identifier-aware, hard-negative-aware retrieval and artifact reuse over
  real tool/trace trajectories, with exact-versus-semantic ablations and
  abstention as a first-class metric.

## Next empirical gate

Before fine-tuning an embedding model, build a reviewed 100–300-query slice
with the five negative types above, then compare:

1. frozen BGE + exact metadata gate;
2. frozen BGE + cross-encoder reranker;
3. domain-adapted bi-encoder with re-mined negatives;
4. artifact/alias graph gate + hybrid retrieval;
5. a cheap model that classifies intent and chooses the retrieval lane.

Promotion requires held-out R@1/R@20, MRR, NIL false-positive rate, alias
accuracy, version disambiguation, and answer-level claim support. A retrieval
lift without safer abstention is not a production win.
