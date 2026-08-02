# WMH-BIRD exposure counterfactuals and termhood retrieval (2026-08-09)

## Question

Can schema tables exposed to a SQL agent but not used by its recorded query
become outcome-backed hard negatives, and does the modernized
Termolator/TermSuite-style termhood signal improve table retrieval on the same
trace cohort?

## Protocol

- Select one deterministic `reward=1.0` trace per base task, rather than
  treating repeated model runs as independent tasks.
- Independently replay the recorded SQL against the pinned BIRD mini-dev
  SQLite archive.
- For every exposed-but-unused table, replace each table used by the recorded
  SQL and replay the counterfactual.
- Label only the counterfactual operation: execution error, result mismatch, or
  result match. These labels measure interchangeability under that SQL; they do
  not assert semantic irrelevance to the user's question.
- On a deterministic within-database holdout, compare exposed-table lexical
  retrieval with the same ranker plus train-only termhood-selected
  question-phrase associations. The alias field is search-only.

## Results

| Measure | Result |
|---|---:|
| Selected successful task traces | 149 |
| Database families | 11 |
| Independent base replays | 149/149 succeeded |
| Counterfactual pairs | 1,236 |
| Counterfactual execution errors | 1,210 (97.896%) |
| Counterfactual result mismatches | 22 (1.780%) |
| Counterfactual result matches | 4 (0.324%) |

Retrieval was evaluated on 71 held-out task cases:

| Arm | MRR | Recall@1 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|
| Exposed-table lexical | .775660 | .676056 | .887324 | 1.000000 |
| + termhood alias field | .788514 | .676056 | .929577 | 1.000000 |

The termhood field improved MRR by `+.012854` and Recall@5 by `+4.2253`
percentage points, with no Recall@1 change. This is a useful candidate-recall
signal, not evidence that a term is a reviewed corporate alias.

## Interpretation

The experiment supports retaining exposure-derived candidates as a source of
replay-checked compatibility negatives. Most exposed tables could not replace
the recorded table without an execution error; the rest mostly changed the
result. The four result-preserving substitutions are ambiguous and must not be
promoted as equivalent artifacts without a semantic or human label.

The older termhood port has a small positive effect at deeper retrieval on a
larger trace cohort than the earlier 13-case proxy. It still does not justify
automatic ontology, memory, embedding, or skill updates. The required product
shape remains:

```text
exposed schema candidates
  -> exact/scope filter
  -> termhood-assisted candidate recall
  -> identifier-aware ranking
  -> independent SQL replay
  -> SME/intent adjudication before semantic promotion
```

## Claim boundary

This is not a semantic-negative benchmark. Tables can be exposed and unused
because of authority, cost, redundancy, or a valid alternative query plan.
Counterfactual replacement tests only whether the table is interchangeable in
the recorded SQL under the pinned database. Enterprise alias quality,
cross-user transfer, changed-schema behavior, and user outcomes remain open.

## Receipts and code

- [content-free result](../results/wmh-bird-exposure-counterfactual-2026-08-09.json)
- [independent verification](../results/wmh-bird-exposure-counterfactual-verification-2026-08-09.json)
- [`wmh_bird_exposure_counterfactual.py`](../../wmh_bird_exposure_counterfactual.py)
- [`verify_wmh_bird_exposure_counterfactual.py`](../../verify_wmh_bird_exposure_counterfactual.py)
- [`test_wmh_bird_exposure_counterfactual.py`](../../tests/test_wmh_bird_exposure_counterfactual.py)
