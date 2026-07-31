# BIRD-SQL trace-mined procedure frontier checkpoint (2026-07-31)

This is the expanded independent frontier-model factorial following the
underpowered six-task pilot. The preregistration is
`configs/experiments/bird-sql-skill-factorial-v1-2026-07-31.json`; the
trace-mined procedure was frozen from disjoint evidence families before any
held-out call. Calls used `gpt-5.6-luna` through the Codex subscription
harness. Gold SQL and raw model responses were kept outside the repository;
the committed receipt contains hashes and aggregate outcomes only.

## Design

- Held-out families: `card_games`, `formula_1`, `financial`, and
  `debit_card_specializing`.
- Five tasks per family, each run in three paired arms: no skill, formatting
  placebo, and trace-mined procedure (60 episodes total).
- The independent verifier used fresh immutable read-only SQLite connections
  and duplicated the SQL extraction, bounded execution, and ordered/unordered
  comparison logic. It verified all 60 rows and the aggregate receipt.

## Result

| arm | episodes | exact | unordered | mismatches | candidate errors |
|---|---:|---:|---:|---:|---:|
| no skill | 20 | 3 | 0 | 16 | 1 |
| formatting placebo | 20 | 4 | 0 | 15 | 1 |
| trace-mined procedure | 20 | 3 | 0 | 16 | 1 |

The trace-mined arm did not improve exact-match accuracy over no skill (3/20
versus 3/20), and it trailed the formatting placebo (3/20 versus 4/20). The
three candidate errors are the same bounded gold-result failure in each arm;
they are retained as errors rather than silently dropped. The independent
verifier reports those diagnostics and confirms that the sealed receipt’s
aggregate semantics match.

This is evidence of **no positive lift in this checkpoint**, not proof that
trace-mined skill improvement is ineffective in general: the cohort is still
small, the horizon is one-shot text-to-SQL, and the procedure was intentionally
simple. No causal skill benefit is claimed, no skill is promoted, and no
Frankengate integration is authorized. A subsequent experiment should use a
larger paired cohort and a task horizon that tests whether a mined procedure
improves repair, clarification, and multi-step execution rather than only one
SQL emission.

Artifacts:

- Aggregate receipt: `../results/bird-sql-skill-factorial-powered-2026-07-31.json`
- Independent verification: `../results/bird-sql-skill-factorial-powered-verification-2026-07-31.json`
- Raw responses remain at the local sealed path used by the run and are not
  committed.
