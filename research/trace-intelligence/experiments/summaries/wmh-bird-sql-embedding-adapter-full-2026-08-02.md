# WMH-BIRD full odd-half embedding adaptation

**Status:** completed and independently verified; public SQL-table proxy only  
**Question:** does replay-confirmed hard-negative supervision improve a frozen
embedding representation when the evaluation is expanded beyond the original
44-task slice?

## Protocol

The pinned WMH-BIRD trace JSONL matched the manifest hashes. The cached BIRD
mini-dev archive was materialized into 11 replayable SQLite databases. The
adapter trains on the deterministic even half of each database and evaluates
on every available odd-half task (`77` train, `71` evaluation). It uses the
same Nomic embedding model and pairwise hinge adapter as the original cohort.
Positive labels are recorded SQL tables plus independently replay-confirmed
result-preserving substitutions. Non-compatible exposed tables are training
negatives. No raw prompts, SQL, observations, or database files are committed.

## Results

| arm | strict MRR | Recall@1 | Recall@5 | compatible selected rate | mean invalid selected |
|---|---:|---:|---:|---:|---:|
| lexical | `.772686` | `.676056` | `.887324` | `.380080` | `3.830986` |
| frozen Nomic | `.935915` | `.901408` | `1.000000` | `.401207` | `3.661972` |
| fold-local adapter | `.939554` | `.901408` | `.985915` | `.401207` | `3.661972` |

Relative to frozen Nomic, the adapter gained only `.003639` MRR, had no
Recall@1 gain, lost `.014085` Recall@5, and did not reduce invalid selections.
The earlier 44-task slice showed a larger rank-one lift (`.940152 → .947917`),
which does not survive as a meaningful broad-cohort improvement.

The result is not a failure of all domain adaptation. It shows that this
particular supervision and representation can make a narrow ranking adjustment
without improving compatibility safety or broad recall. The public proxy has
database/table labels and replay outcomes, but no reviewed corporate aliases,
same-surface wrong-system labels, temporal replacements, principal/team
holdouts, or human intent outcomes.

## Decision

Keep the adapter as a shadow reranker behind exact identifiers, schema scope,
and independent replay. Do not promote it as a corporate embedding model. The
next decisive study must add reviewed alias/NIL and wrong-system cases, then
measure downstream reusable-artifact utility on a changed system—not merely
table rank.

## Receipts

- [full content-free result](../results/wmh-bird-sql-embedding-adapter-full-2026-08-02.json)
- [independent verification](../results/wmh-bird-sql-embedding-adapter-full-verification-2026-08-02.json)
- [`wmh_bird_sql_embedding_adapter_cohort.py`](../../wmh_bird_sql_embedding_adapter_cohort.py)
- [`verify_wmh_bird_sql_embedding_adapter_cohort.py`](../../verify_wmh_bird_sql_embedding_adapter_cohort.py)
- [pinned dataset manifest](../../configs/datasets/wmh-bird-sql-traces.json)

