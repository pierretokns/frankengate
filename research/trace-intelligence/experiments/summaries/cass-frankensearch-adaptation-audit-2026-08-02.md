# CASS / Frankensearch adaptation audit

**Source:** CASS (`coding_agent_session_search`) at commit
`8844ba66e24d18c54ece51d06fd6fede6002a60e` (v0.6.23)  
**Status:** source-level architecture audit; not a Frankengate efficacy result

## What CASS actually contributes

The repository is more disciplined than a generic “put chat logs in a vector
database” design. Its useful concepts are explicit in the source:

| CASS concept | Source-level contract | Frankengate adaptation |
|---|---|---|
| Lexical floor | `HybridPreferred` always keeps lexical search usable; semantic quality is opportunistic. `StrictSemantic` is opt-in and never the default. | Never let a missing/stale embedding model block trace search or artifact lookup. Keep exact identifiers and SQL/tool names queryable. |
| Progressive two-tier search | A fast in-process tier returns immediately; a quality daemon refines a bounded shortlist. The default refinement budget is 100 documents. | Use cheap lexical/identifier/scope retrieval first, then spend frontier or quality-model budget only on ambiguous/high-value candidates. |
| Immutable semantic generations | A completed generation is published through a compare-and-swap `current.json` pointer. Mutable backfill state never implies runtime readiness. | Make embedding, alias, graph, and reranker generations immutable and selected atomically. A partially rebuilt index must never become a source of truth. |
| Explicit invalidation | Artifacts fingerprint model revision, semantic schema, chunking strategy, document count, database fingerprint, and readiness. Stale and incompatible states are distinct. | Add trace schema, parser version, authority epoch, deletion watermark, and artifact-verifier version to every derivative index. |
| Derivative storage budget | Semantic artifacts are rebuildable; eviction removes HNSW, quality vectors, fast vectors, and models before the canonical SQLite/lexical index. | Keep canonical Postgres/trace rows authoritative. Treat vectors and graph projections as disposable caches with measurable rebuild cost. |
| Metadata-first lessons | A lesson has a stable content-derived ID, topic/project scope, kind, confidence, provenance, freshness, and lifecycle (`active`, `superseded`, `outdated`). Raw session text is not part of the core record. | Store reusable SQL/tool capsules and “failed approach” records as typed, scoped, versioned proposals—not untyped memories. Preserve internal content for authorized admins, but keep audience/retention policy explicit. |
| Evidence extraction boundary | CASS extracts lessons from landed commits, closed beads, and proof runs, redacts sensitive text, and keeps provenance refs separate from summaries. | Replace “model liked this trace” with terminal evidence: successful replay, accepted review, release, rollback, or explicit user confirmation. Model output remains a proposal. |
| Trust correlation | Trust is anchored to explicit bead/commit identifiers and release containment; workspace or temporal coincidence never fabricates trust, and correlation does not silently reorder results. | Link an artifact/eval/skill to exact trace, verifier, change-set, and release evidence. Trust metadata should explain why an item is trustworthy, not become an unexamined ranking shortcut. |
| Metamorphic/fixture discipline | CASS carries golden fixtures and metamorphic tests for search filters, casing, corpus shape, result ordering, and storage failures. | Add metamorphic tests for aliases, same-surface wrong-system cases, temporal renames, stale authority, deletion, and NIL queries before training or promotion. |

## What this explains about our results

Our EnterpriseRAG and NL2SQL experiments already show why CASS’s lexical floor
and progressive cascade are important:

- source/identifier filters produce the largest safety and rank gains before
  semantic review;
- generic dense retrieval can have low candidate recall even when a frontier
  model is good at ordering the candidates it receives;
- a semantic index that is unavailable, stale, or trained on the wrong aliases
  must degrade to exact/lexical search rather than silently returning an empty
  or authoritative-looking answer;
- derived “lesson” or “memory” records need supersession and provenance, or
  old successful queries become misleading after schema/tool drift.

CASS does **not** solve the hardest Frankengate questions. Its lesson graph is
fed by commits/beads/proofs, not independently labeled user intent, semantic
alias identity, cross-user task equivalence, or prospective skill utility. Its
two-tier embeddings improve search responsiveness and candidate recall, but do
not prove a corporate ontology or a safe reusable SQL artifact. Those remain
open gates in the [enterprise semantic cohort contract](../../configs/studies/enterprise-semantic-cohort-v1.json).

## Recommended Frankengate design

```text
canonical trace / artifact / authority rows
  -> exact identifiers + lexical index (always available)
  -> fast derivative embedding tier (optional, bounded)
  -> quality reranker or frontier review (shortlist only)
  -> identity / temporal / authority / NIL checks
  -> independent replay and human outcome
  -> immutable proposal generation
  -> atomic promotion or supersession
```

The key CASS lesson is not “use its embedding model.” It is to make the
semantic layer a restartable, versioned, budgeted derivative of an authoritative
record, while retaining a fast exact path and an explicit lifecycle for every
learned item.

## Next empirical test

Run a CASS-shaped cascade on the existing trace cohort, keeping the same frozen
query/document candidates across arms:

1. lexical + identifier + scope only;
2. fast embedding shortlist;
3. fast embedding plus quality reranker;
4. the same three arms with CASS-style lesson supersession and provenance;
5. injected stale, deleted, renamed, and NIL cases.

Report Recall@20/MRR, collision-before-target, NIL abstention, stale acceptance,
replay success, correction burden, latency, and rebuild cost separately. Do not
call a faster or more stable index an ontology or skill result.

## Source links

- [CASS repository](https://github.com/Dicklesworthstone/coding_agent_session_search)
- [Two-tier progressive search](https://github.com/Dicklesworthstone/coding_agent_session_search/blob/8844ba66e24d18c54ece51d06fd6fede6002a60e/src/search/two_tier_search.rs)
- [Semantic policy and invalidation](https://github.com/Dicklesworthstone/coding_agent_session_search/blob/8844ba66e24d18c54ece51d06fd6fede6002a60e/src/search/policy.rs)
- [Immutable semantic manifest](https://github.com/Dicklesworthstone/coding_agent_session_search/blob/8844ba66e24d18c54ece51d06fd6fede6002a60e/src/search/semantic_manifest.rs)
- [Durable lessons graph](https://github.com/Dicklesworthstone/coding_agent_session_search/blob/8844ba66e24d18c54ece51d06fd6fede6002a60e/src/lessons.rs)
- [Lesson extraction and redaction](https://github.com/Dicklesworthstone/coding_agent_session_search/blob/8844ba66e24d18c54ece51d06fd6fede6002a60e/src/lessons_extraction.rs)
- [Identifier-anchored trust correlation](https://github.com/Dicklesworthstone/coding_agent_session_search/blob/8844ba66e24d18c54ece51d06fd6fede6002a60e/src/search/trust_correlation.rs)

