# BIRD-SQL trace-mined procedure factorial, 40 held-out tasks (2026-08-06)

## Protocol

This is an expanded, independent family-disjoint replay of the earlier
20-task checkpoint. The same frozen procedure, evidence-family mining boundary,
Codex-subscription model (`gpt-5.6-luna`), read-only SQLite evaluator, and
three arms were retained:

- no skill;
- formatting-only placebo;
- trace-mined procedure.

The 40 held-out tasks are the first ten sorted tasks from each of
`card_games`, `formula_1`, `financial`, and `debit_card_specializing`. Gold SQL
and raw responses stayed outside the repository. The committed result contains
task hashes, response hashes, outcomes, and timing only.

## Result

| Arm | Exact | Exact rate | Candidate errors | Mean episode latency |
|---|---:|---:|---:|---:|
| No skill | 8/40 | 20.0% | 1 | 10.306 s |
| Formatting placebo | 5/40 | 12.5% | 1 | 10.590 s |
| Trace-mined procedure | 8/40 | 20.0% | 2 | 11.102 s |

Paired exact-match comparisons:

- Trace-mined versus no-skill: **1 win, 1 loss, 38 ties**, exact sign-test
  `p=1.0`.
- Trace-mined versus formatting placebo: **3 wins, 0 losses, 37 ties**, exact
  sign-test `p=0.25`.

The independent evaluator recomputed all `120` episodes and matched the
runner receipt. It reported three diagnostic gold-execution errors while
preserving the runner's bounded outcome semantics.

## Interpretation

The larger run still shows **no statistically supported skill lift** over
no-skill. The procedure is also about `7.7%` slower than no-skill and has one
additional candidate error. The result is a stronger negative checkpoint, not
a universal disproof of skill learning: it uses one public SQL proxy cohort,
one frozen procedure, and one frontier model. It does establish that this
trace-mined procedure should not be promoted or integrated into Frankengate.

The next valid skill experiment should change the task horizon or artifact
consumer—multi-turn repair, clarification, or a sequential task chain—rather
than simply rerunning the same one-shot SQL prompt more times.

## Receipts

- [aggregate result](../results/bird-sql-skill-factorial-40-2026-08-06.json)
- [independent verification](../results/bird-sql-skill-factorial-40-2026-08-06-verification.json)
- [paired analysis](../results/bird-sql-skill-factorial-40-2026-08-06-paired.json)
- [frozen procedure](../candidates/bird-sql-trace-mined-procedure-v1.md)

