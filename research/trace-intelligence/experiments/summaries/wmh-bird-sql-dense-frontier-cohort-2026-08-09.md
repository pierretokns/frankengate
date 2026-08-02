# WMH-BIRD dense versus frontier SQL exploration

## Question

On the same task-disjoint, replay-backed cohort, does a local embedding model
provide useful table recall, and does frontier review add value by removing
incompatible candidates rather than merely changing rank order?

## Protocol

This is the exact 44-case cohort used by the prior task-disjoint explorer
study: four odd-half tasks per database across eleven database families. The
candidate pool is every table exposed in the trace. The evaluator retains the
recorded SQL table set and independently replay-confirmed compatible
substitutions.

The three arms are:

- lexical token overlap;
- local `nomic-embed-text:latest` vectors over database/question and
  database/table text;
- Luna frontier exploration over the question and exposed table names only.

The frontier never sees SQL, target tables, or replay outcomes. All replay
labels are evaluator-only. There were 44 frontier calls, zero failures, and
all raw model receipts remain external.

## Result

| Arm | Strict MRR | Recall@1 | Recall@5 | Replay-compatible selected rate | Mean selected | Mean invalid selected |
|---|---:|---:|---:|---:|---:|---:|
| Lexical | `.796266` | `.704545` | `.886364` | `.391153` | `5.545` | `3.727` |
| Dense Nomic | `.940152` | `.909091` | `1.0` | `.408198` | `5.545` | `3.591` |
| Frontier Luna | `.954545` | `.909091` | `1.0` | `.928030` | `2.000` | `.205` |

Dense retrieval substantially improved ordering over lexical and matched the
frontier's Recall@1 on this public proxy, but it still returned a large noisy
shortlist. Frontier review added little Recall@1 beyond dense retrieval, yet
removed most incompatible candidates and cut the shortlist from about 5.5 to
2 tables. The improvement is therefore primarily **precision/noise reduction**,
not evidence that frontier reasoning discovers more target tables.

The pooled result hides family variation. Dense was stronger than frontier on
Debit Card Specializing, Thrombosis Prediction, and Toxicology, while frontier
was stronger on Formula 1 and Student Club. This is another reason to keep
family-stratified evaluation and avoid a universal frontier policy.

## Interpretation

This is the clearest current embedding-versus-model cascade result:

```text
structured scope
  -> dense or lexical candidate recall
  -> frontier shortlist compression
  -> independent replay compatibility
```

It supports using a local embedding model as an optional broad-recall stage and
frontier review as a selective compression/ambiguity stage. It does not justify
a custom enterprise embedding, semantic alias promotion, or hot-path frontier
scoring. The cohort is public WMH-BIRD data with hinted schema exposure and no
enterprise authority, human intent, or changed-system outcomes; the result must
be repeated on reviewed corporate hard negatives before deployment claims.

Receipts:

- [content-free result](../results/wmh-bird-sql-dense-frontier-cohort-2026-08-09.json)
- [independent verification](../results/wmh-bird-sql-dense-frontier-cohort-verification-2026-08-09.json)
- [`wmh_bird_sql_dense_frontier_cohort.py`](../../wmh_bird_sql_dense_frontier_cohort.py)
