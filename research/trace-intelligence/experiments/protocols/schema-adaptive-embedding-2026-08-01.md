# Schema-adaptive embedding and alias-retrieval protocol

**Status:** preregistered design; no outcome claim.

## Motivation

The neutral MATM adapter result used trajectory-similarity proxy labels. It is
not a fair test of the newer schema-retrieval recipe, which synthesizes
question-like positives from the target schema and mines granularity-aware hard
negatives. This protocol tests that recipe on the public Defog/BIRD schemas
before applying any method to private traces.

## Corpus and units

- Use only hash-pinned Defog/BIRD schemas and public question/SQL rows.
- Index table-level and column-level documents separately, retaining database,
  schema, table, column, type, lineage/version, and source row hashes.
- Never use held-out gold SQL, target answers, or target-task identifiers while
  constructing a candidate library.
- Preserve a separate alias/NIL label layer; retrieval rank is not semantic
  alias truth.

## Positives and hard negatives

1. Generate question-like positives from training-schema metadata using frozen
   templates plus a recorded model-generated paraphrase pass.
2. Add naturally occurring training questions only when their target table or
   column is independently resolved from the training SQL.
3. Mine hard negatives from same-scope sibling tables/columns, same-surface
   identifiers in other databases, table/column granularity conflicts, stale or
   renamed schema versions, and tool-contract conflicts.
4. Obtain two independent labels on the evaluation slice:
   `positive`, `wrong_scope`, `stale`, `nil`, or `unclear`. Preserve abstention.

## Arms

- exact identifier plus known database scope;
- lexical/full-text retrieval;
- frozen general-purpose embedding;
- corpus-adaptive embedding trained on schema-generated positives and
  granularity-aware hard negatives;
- structured hybrid: exact/lexical/dense plus identifier, scope, lineage, and
  granularity features;
- optional frontier reranker applied only to the frozen top-k candidates.

The adaptive arm may use contrastive fine-tuning or a lightweight adapter, but
the backbone, training budget, and early-stopping rule must be frozen before
the held-out split is opened. No arm may use the held-out labels for candidate
construction.

## Splits and primary metrics

Use leave-one-database-family-out, query-template holdout, and where available
user/project/time holdouts. Report per-family and pooled:

- Recall@1/5/10, MRR, and nDCG@10 at table and column level;
- collision-before-target and wrong-scope acceptance;
- NIL/unclear abstention precision and coverage;
- query/document latency, embedding cost, and reranker cost; and
- the fraction of top candidates that survive independent semantic and
  authority validation.

## Downstream gate

The retrieval winner is not a production recommendation until its top
candidates are converted into validation-carrying SQL/tool artifacts and
replayed on a changed governed system. Promotion requires retrieval lift over
exact+scope and the frozen generic baseline, zero release-blocking false
semantic acceptance, and a positive paired changed-system outcome or a typed
null. A Recall@10 gain without artifact utility remains a research result.

## Interpretation

- A positive result would support schema-specific adaptation, not a universal
  corporate embedding model.
- A null result would be informative only if schema-generated positives,
  granularity negatives, and family-held-out splits were actually implemented.
- Any benefit that disappears after scope/identifier features are added should
  be reported as structured retrieval value, not embedding value.
