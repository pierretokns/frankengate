# Retrieval → compatibility → replay composition decision (2026-08-09)

This note joins the strongest existing retrieval and changed-system receipts.
It is deliberately not a new pooled benchmark: the cohorts, labels, and
evaluators differ, so the numbers must not be combined statistically.

## Evidence joined

1. The same-candidate PostgreSQL retrieval run loaded 145 documents and 1,024-
   dimensional vectors under forced RLS. Exact pgvector reached Recall@1
   `.338`, Recall@5 `.561`, and MRR `.666`; PostgreSQL FTS reached Recall@1
   `.061`. Withdrawn and soft-deleted rows disappeared before ranking, and the
   denied candidate matrix was zero.
2. The changed-system artifact fixture compared compatibility policies. Strict
   fingerprints accepted `1/5` cases, name-only compatibility accepted `5/5`
   but made two unsafe semantic accepts, and semantic-ID compatibility accepted
   `3/5` with zero unsafe accepts.
3. The validated-subplan fixture reached `3/3` semantically correct accepts
   under semantic-ID admission and `5/5` name-only accepts with two unsafe
   accepts.
4. The BIRD exposure/replay studies show why a candidate that merely executes
   is not enough: among 1,236 exposed-table substitutions, 1,210 errored, 22
   changed the result, and only four preserved the result.

## Architecture decision

The systems compose in this order:

```text
trace fields + principal/project/time scope
  -> exact identifiers and authority/RLS filter
  -> lexical / FTS / cheap structured reranker
  -> optional pgvector or other dense candidate expansion
  -> semantic-ID/schema/tool compatibility gate
  -> independent execution or replay verifier
  -> result-shape/outcome check
  -> versioned artifact, eval, or skill proposal
```

Retrieval is allowed to increase candidate recall; it is never allowed to
authorize, adapt, or publish an artifact. Semantic-ID compatibility is the
minimum safe bridge across schema evolution. A name-only match can be useful
for generating a review candidate, but it must fail closed before execution.

## What this proves and does not prove

**Supported:** PostgreSQL can combine vector retrieval with policy filtering in
a small local fixture; semantic IDs prevent the two tested classes of silent
schema collision; replay can distinguish execution failure from result
preservation.

**Not supported:** Aurora scale or failover, production concurrency, human
semantic labels, enterprise prevalence, cross-user benefit, or causal skill
improvement. The retrieval and changed-system fixtures are independent and
must not be reported as one end-to-end enterprise result.

## Next decisive combined test

Use one consented changed-system cohort and freeze the same artifact pool across
all arms: exact/structured, lexical, dense, hybrid, frontier review, and
regeneration. For each candidate, record pre-ranking authorization, semantic
mapping, replay result, stale/temporal status, reviewer label, latency, and
next-task utility. Include same-surface wrong-system, approved rename,
result-preserving alternative, temporal replacement, and true-NIL cases. The
promotion gate is a paired downstream lift with zero unsafe accepts—not a
retrieval metric alone.

## Receipts

- [PostgreSQL joint retrieval](codetracebench-e2-postgres-joint-retrieval-2026-07-30.md)
- [changed-system replay](artifact-changed-system-replay-2026-08-03.md)
- [changed-system subplan replay](artifact-subplan-changed-system-replay-2026-08-05.md)
- [BIRD exposure counterfactual](wmh-bird-exposure-counterfactual-2026-08-09.md)
- [embedding/model cascade decision](embedding-model-cascade-decision-2026-08-09.md)

