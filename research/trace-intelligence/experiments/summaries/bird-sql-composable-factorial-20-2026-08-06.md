# Family-disjoint BIRD-SQL validated-subplan composition (2026-08-06)

## Protocol

This replay tests whether the earlier five-task broker composition result
transfers across database families. A validated library was built from four
evidence families (`superhero`, `toxicology`, `student_club`, and
`california_schools`) only. It was evaluated on 20 tasks from four disjoint
target families (`card_games`, `formula_1`, `financial`, and
`debit_card_specializing`). Gold SQL and target results were sealed from the
model. Arms were fresh generation, formatting placebo, and composable-subplan
library. The library contained 16 validated source examples and was instructed
to compose compatible patterns rather than copy whole queries.

## Result

| Arm | Exact | Candidate errors | Mean episode latency |
|---|---:|---:|---:|
| No skill | 3/20 | 1 | 10.656s |
| Formatting placebo | 3/20 | 2 | 12.112s |
| Composable subplan library | 4/20 | 2 | 11.446s |

The independent evaluator recomputed all 60 episodes and matched the receipt.
The composable arm had **one paired win and zero losses** against each control,
with 19 ties in each comparison. The exact paired sign test is `p=1.0` because
there was only one discordant task.

## Interpretation

This is a **directionally encouraging but underpowered transfer signal**. It
does not reproduce the dramatic 10/10 same-family broker result, but it also
does not collapse to the one-shot procedure null. The result supports testing
validated subplans as a separate artifact granularity, not promoting a generic
memory or embedding layer. No skill or library was promoted.

The next gate is a larger multi-family composition study with multiple frozen
libraries, repeated seeds, explicit NIL/irrelevant-library cases, and changed-
schema replay. The library must remain scope- and provenance-bound; source
examples from an unrelated system cannot be treated as semantic aliases.

## Receipts

- [aggregate result](../results/bird-sql-composable-factorial-20-2026-08-06.json)
- [independent verification](../results/bird-sql-composable-factorial-20-2026-08-06-verification.json)
- [paired analysis](../results/bird-sql-composable-factorial-20-2026-08-06-paired.json)
- [runner](../../bird_sql_composable_factorial.py)

