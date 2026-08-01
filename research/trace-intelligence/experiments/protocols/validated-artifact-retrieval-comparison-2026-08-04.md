# Validated-artifact retrieval comparison — 2026-08-04

## Question

The first unpaired artifact screen found that same-database lexical nearest-
question retrieval transferred to `0/10` held-out Defog targets. That result
does not distinguish a bad artifact-reuse idea from a bad retriever. This
protocol compares retrieval families on the same fixed target/source cohort.

## Cohort and leakage boundary

- Targets are the ten broker/car-dealership `questions_gen_postgres.csv` tasks
  in the pinned Defog enterprise manifest.
- The artifact pool contains only validated SQL from the target database's
  `instruct_basic_postgres.csv` and `instruct_advanced_postgres.csv` rows.
- No target question, SQL, result, or task identifier is admitted to the
  source pool.
- A cross-scope pool is also evaluated as a negative control. Its candidates
  come from both databases and must not outrank an in-scope artifact.
- Synthetic NIL controls scope-swap each target into the other database only
  when the target's referenced tables are absent from the alternate database's
  validated artifact schema surface. These are structural NILs, not human
  intent labels.

## Retrieval arms

1. `lexical_scoped`: question-token overlap after database scope filtering.
2. `dense_scoped`: frozen `nomic-embed-text:latest` question embeddings after
   scope filtering.
3. `identifier_scoped`: lexical question overlap plus source SQL table/column
   identifier overlap after scope filtering.
4. `hybrid_scoped`: reciprocal-rank fusion of lexical and dense rankings after
   scope filtering.
5. `lexical_all`, `dense_all`, and `hybrid_all`: the same selectors without a
   scope filter, measuring wrong-system contamination.
6. `identifier_gate_scoped`: identifier-aware ranking that abstains when no
   candidate has a positive identifier/surface signal. This is the only
   deterministic abstention arm; it is evaluated for coverage/abstention, not
   as a semantic oracle.

All ranking ties are broken by the content-free task ID. Scores and embeddings
are generated before semantic outcomes are read. The evaluator executes up to
the top three distinct same-scope candidates per target under the governed
PostgreSQL authority and independently compares bounded result content to the
gold result. A cross-scope selection is recorded as a scope mismatch and is
not executed against the target database.

## Primary endpoints

- top-1 semantic transfer;
- any semantic transfer in top-3;
- scope-correct top-1 selection;
- structural-NIL abstention rate and non-abstaining selection rate;
- governed authorization failures and execution errors.

The result is a retrieval-and-execution diagnostic. It does not establish
causal agent utility, enterprise alias truth, or that a stored artifact should
replace regeneration.
