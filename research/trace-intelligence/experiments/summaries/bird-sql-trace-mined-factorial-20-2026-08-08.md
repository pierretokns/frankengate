# Family-disjoint BIRD-SQL replay with validated trace artifacts (2026-08-08)

## Question

Does a library made from **actual recorded tool-call SQL**, admitted only after
independent execution against its own gold outcome, improve one-shot text-to-SQL
on unseen database families? This isolates artifact validity from the earlier
gold-example composition experiment.

## Protocol

- **Target:** 20 held-out tasks, five each from `card_games`, `formula_1`,
  `financial`, and `debit_card_specializing`.
- **Source:** 16 independently validated trace artifacts, four each from the
  disjoint families `superhero`, `toxicology`, `student_club`, and
  `european_football_2`.
- **Arms:** no skill, formatting placebo, and the validated trace-artifact
  library. The model received target schema and question; target gold SQL and
  result values were hidden.
- **Evaluator:** fresh immutable SQLite connections, read-only SQL extraction,
  result comparison, and a 10,000-row/8 MB/2-second bound. One initial target
  was excluded before prompting because its gold result exceeded the bound;
  this prevents an evaluator limitation from becoming an apparent model error.

The source and target families are disjoint. The raw frontier responses remain
outside the repository; only hashes and aggregate outcomes are committed.

## Result

| Arm | Exact result | Mismatch | Candidate execution errors | Mean episode latency |
|---|---:|---:|---:|---:|
| No skill | 3/20 (15%) | 16 | 1 | 10.93 s |
| Formatting placebo | 3/20 (15%) | 17 | 0 | 11.04 s |
| Validated trace-artifact library | 4/20 (20%) | 16 | 0 | 10.41 s |

The trace-library arm had **one exact win, zero exact losses, and 19 paired
ties** against no-skill. It tied the placebo on every task. The no-skill
execution error was a malformed-JSON query (`json_each`); it is counted as an
execution failure, not silently treated as a mismatch or success.

## Interpretation

This is a **small, directionally positive but not promotion-worthy** result:

1. A validated trace artifact library did not hurt transfer on this split and
   produced one additional exact answer.
2. The effect is too small for a causal claim: one discordant task, one model,
   one seed, 20 tasks, and no human intent labels.
3. The result is consistent with the earlier evidence that validated subplans
   may be useful, while generic prose/procedure skills are not yet useful. It
   does not establish that whole-query retrieval, dense embeddings, or a
   corporate skill library improves user outcomes.
4. The library was cross-family and therefore intentionally weakly related;
   this measures safe transfer, not repeated-workstream reuse. A stronger next
   test needs repeated intents, compatible schema/template families, changed
   database state, and irrelevant-library NIL cases.

**Disposition:** retain validated artifacts as scope-bound, independently
replayable candidates. Do not auto-promote them into a skill, cache, ontology,
or embedding model.

## Receipts and code

- [aggregate receipt](../results/bird-sql-trace-mined-factorial-20-2026-08-08.json)
- [independent verification](../results/bird-sql-trace-mined-factorial-20-2026-08-08-verification.json)
- [`bird_sql_trace_mined_factorial.py`](../../bird_sql_trace_mined_factorial.py)
- [`verify_bird_sql_trace_mined_factorial.py`](../../verify_bird_sql_trace_mined_factorial.py)
- [`test_bird_sql_trace_mined_factorial.py`](../../tests/test_bird_sql_trace_mined_factorial.py)

