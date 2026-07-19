# Domain-adaptive embeddings and secure RAG research
Status: research/architecture input for `bif-kyy.17.12`; no embedding-model promotion is authorized by this document.

## What we are optimizing

The target is not a globally “smarter” vector space. It is higher retrieval quality for
approved, tenant-scoped finance and enterprise terminology while preserving exact
authorization, deletion, provenance, and low-latency serving. Measure recall@k, nDCG,
MRR, answer-supportedness, citation precision, ACL false-positive/false-negative rate,
tail latency, index size, embedding cost, and model drift. Split evaluation by team,
jargon cohort, document age, query intent, and authorization boundary.

## Current research conclusions

- Start with a strong general embedding baseline and hybrid lexical+dense retrieval.
  Finance jargon and identifiers are often exact-match signals; dense retrieval alone
  can hide ticker symbols, version strings, SQL names, and policy IDs.
- Adapt only after collecting sanitized query-document judgments. Useful supervision is
  accepted/rejected retrieval, clicked or cited passages, resolved friction cases,
  human pairwise labels, and hard negatives that are lexically similar but unauthorized
  or semantically wrong.
- Prefer a small adapter/projection or contrastive fine-tune before changing the base
  model. Re-mine hard negatives after each round, retain a frozen holdout, and compare
  against the unadapted baseline. Never infer improvement from cosine similarity alone.
- Fine-tune the generator and the retriever for different reasons. Retrieval adaptation
  improves what is found; generator fine-tuning can improve terminology/style but must
  not become the source of mutable facts that should remain in RAG.
- Embedding model, chunking, tokenizer, normalization, index, and ACL policy are one
  versioned retrieval contract. Re-embedding is a migration with dual-read/shadow and
  rollback, not an in-place background mutation.

## Curation and adaptation loop

1. Capture a privacy-filtered evidence envelope: tenant/team/document IDs, purpose,
   policy revision, redacted query, retrieval candidates, scores, selected citations,
   outcome/evaluator labels, and model/index revisions. Do not store raw prompts,
   outputs, or tokens by default.
2. Build query-document positives and hard negatives from approved sources. Keep user,
   team, document sensitivity, and retention metadata attached to every example.
3. Run lexical, dense, hybrid, and reranker baselines on frozen cohorts. Report slices
   where adaptation helps and harms; require minimum coverage and missingness bounds.
4. Train an adapter/projection or contrastive retriever offline. Candidate artifacts are
   content-addressed and signed; no training worker can publish or change the serving
   model automatically.
5. Shadow the candidate, then sticky-canary it for approved cohorts. Promote only after
   human/MR approval, ACL conformance, deletion tests, cost/latency SLOs, and holdout
   quality gates pass. Roll back the whole retrieval contract on regressions.

NVIDIA's Data Flywheel blueprint is useful for trace-to-dataset serialization,
fine-tuning experiment tracking, artifact versioning, and human-gated promotion. Its
own guidance treats curation and production promotion as human decisions; we retain
that constraint rather than importing autonomous publication.

## Storage options

| Option | Role | Strength | Boundary |
|---|---|---|---|
| SQLite/CASS-style local store | user/team lexical evidence and memory | simple, cheap, deletable, inspectable | not a shared authorization source; optional per-tenant index |
| Aurora PostgreSQL + pgvector | durable control plane and moderate shared index | existing authority, SQL ACL joins, transactions, backups | do not put inference on synchronous DB lookups; benchmark vector scale and vacuum/recall |
| Qdrant/Weaviate/Pinecone | derived large-scale vector index | ANN scale and filtering adapters | credentials, region, deletion, and outage are extra control-plane concerns |
| LightRAG-style graph + vector | entity/relation-aware retrieval | useful for multi-hop enterprise knowledge | graph extraction is another derived sensitive copy; ACL must filter graph edges and chunks before retrieval |

Launch recommendation: Aurora owns document policy, ACL, retention, tombstones, and
model/index manifests; a rebuildable tenant-scoped vector adapter is asynchronous;
SQLite/CASS lexical recall remains available as a simple fallback. Do not make a vector
or graph outage take the gateway data plane down.

## Security contract for chunks and graphs

Every chunk, entity, relation, embedding, and cached result carries tenant, team,
document, sensitivity, purpose, retention, policy revision, source revision, and delete
tombstone identifiers. Authorization is applied before ANN/graph candidate exposure,
before reranking, before snippet assembly, and before caching. A post-filter is not
enough: unauthorized candidates can leak through scores, counts, graph neighborhoods,
or cache hits. Cross-tenant aggregation is opt-in and differential/thresholded.

Deletion revokes the source envelope, tombstones all derived embeddings/graph nodes,
invalidates caches, and is verified by an index rebuild/readback test. Model or ACL
revision changes use a dual-read/shadow window and a fail-closed policy when the index
is stale or provenance is unknown.

## Initial experiment matrix

Compare (1) lexical BM25, (2) baseline dense, (3) hybrid, (4) hybrid+rereanker, and
(5) hybrid with a small domain adapter. Use sanitized finance and enterprise cohorts,
hard negatives, ACL boundary cases, deleted documents, jargon/OOV cases, and stale-index
cases. Record quality, p50/p95 latency, memory, storage, and embedding cost. Only the
experiment bundle—not the production gateway—may call training or large-model judges.
