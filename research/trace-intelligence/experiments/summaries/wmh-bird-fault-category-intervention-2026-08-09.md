# WMH-BIRD fault-category checklist intervention (2026-08-09)

## Question

Does a short checklist derived from first-fault categories in recorded SQL-agent
trajectories improve one-shot text-to-SQL on database families withheld from
the mined traces?

## Protocol

- **Target:** four tasks, two each from the family-disjoint `financial` and
  `student_club` families.
- **Arms:** no skill, a formatting-only placebo, and the frozen
  [`fault-category checklist`](../procedures/wmh-bird-fault-category-checklist-v1.md).
- **Model/harness:** `gpt-5.6-luna` through the Codex CLI subscription.
- **Information boundary:** the proposer received only the task and schema;
  gold SQL and gold results remained in a separate evaluator.
- **Evaluator:** independent fresh SQLite connections and a duplicated
  verifier. Raw frontier responses remain outside the repository.

## Result

| Arm | Exact | Unordered-only | Mismatch | Episodes | Total latency |
|---|---:|---:|---:|---:|---:|
| No skill | 0 | 0 | 4 | 4 | 45.433 s |
| Formatting placebo | 0 | 0 | 4 | 4 | 43.473 s |
| Fault-category checklist | 0 | 0 | 4 | 4 | 38.164 s |

Independent verification passed for all 12 rows and recomputed the same
aggregate counts. The checklist arm was faster in this run, but the sample is
far too small for a latency or quality claim.

## Interpretation

This is a **valid harness run but an underpowered null result**, not evidence
that fault-category procedures are useless. The selected tasks also expose two
important evaluator lessons:

1. A model can produce a semantically plausible query while failing the strict
   result contract—for example, returning all transaction columns when the
   target asks for transaction IDs.
2. “Second-highest branch” can require matching the second-highest *value*,
   including ties; selecting one district by `OFFSET` is not equivalent.

The procedure therefore did not earn promotion. The next intervention should
use a larger, task-disjoint cohort stratified by first-fault category and score
both execution semantics and requested projection, with explicit tie/NULL
cases. A successful run must beat both no-skill and formatting placebo with
paired confidence intervals and no material cost or reliability regression.

## Receipts

- Aggregate receipt: `/private/tmp/wmh-bird-fault-category-four-task.json`
- Independent verification: `/private/tmp/wmh-bird-fault-category-four-task-verification.json`
- Raw responses (not committed): `/private/tmp/wmh-bird-fault-category-four-task-raw.json`

