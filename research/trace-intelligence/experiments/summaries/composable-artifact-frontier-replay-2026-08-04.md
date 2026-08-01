# Composable validated-artifact frontier replay — 2026-08-04

## Design

The natural held-out artifact pool contained no semantically reusable whole
query. This replay instead exposed a frontier agent to an external library of
18 governed-success broker examples and instructed it to reuse compatible
tables, joins, filters, and aggregation patterns as **subplans**, while
inspecting the current schema and generating a new query. The target questions
were the five broker `questions_gen` tasks excluded from the source files.

Two direct Codex/Luna seeds used the identical source/target split, candidate
text, authority, tool contract, and limits. Each seed had no-skill,
formatting-placebo, and composable-subplan arms. The first receipt path was
quarantined after a concurrent writer overwrote it; the results below use the
unique seed-840000 rerun and the unique seed-850000 receipt.

## Aggregate result

| Arm | Semantic correctness | SQL attempts | Tool calls | Authority-valid | Unauthorized observations |
| --- | ---: | ---: | ---: | ---: | ---: |
| No skill / fresh generation | 5/10 | 15 | 35 | 10/10 | 0 |
| Formatting placebo | 5/10 | 16 | 36 | 10/10 | 0 |
| Composable subplan library | **10/10** | **10** | **30** | 10/10 | 0 |

At the five unique task level, the composable arm had three stable wins, zero
stable losses, and two ties against each control. Repeated seeds are not
independent tasks and are reported as a variance check, not as a powered
significance test. Both independent PostgreSQL semantic verifiers passed with
no stored/recomputed mismatches or errors.

## Interpretation

This is the first positive result after the library-coverage null: validated
examples that are decomposed and composed by a frontier agent can improve
future-task outcomes when complete-query retrieval has no exact answer. The
result supports storing reusable artifacts at multiple granularities—whole
query, parameterized template, and typed subplan—rather than only storing
finished SQL strings.

It is not yet an enterprise skill-learning claim. The cohort is five tasks in
one database family, the examples include source SQL, the prompt is a designed
candidate rather than a naturally mined skill, and the controls are not a
changed-schema or cross-family replay. The candidate remains promotion-
ineligible until it beats fresh generation on larger family/time/project
holdouts, with SME-labeled relevance, explicit NILs, cost/latency accounting,
and changed-system replay.

Receipts:

- [aggregate](../results/composable-artifact-frontier-replay-2026-08-04-aggregate-rerun.json)
- [seed 840000](../results/composable-artifact-frontier-replay-2026-08-04-seed840000-rerun.json)
- [seed 850000](../results/composable-artifact-frontier-replay-2026-08-04-seed850000.json)
- [seed 840000 semantic verification](../results/composable-artifact-frontier-replay-2026-08-04-seed840000-rerun-verification.json)
- [seed 850000 semantic verification](../results/composable-artifact-frontier-replay-2026-08-04-seed850000-verification.json)
