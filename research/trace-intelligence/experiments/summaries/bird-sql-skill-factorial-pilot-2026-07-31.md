# BIRD-SQL trace-mined procedure pilot (2026-07-31)

This is the first independent frontier-model intervention pilot from the new
research gate. The preregistration is
`configs/experiments/bird-sql-skill-factorial-v1-2026-07-31.json`; the frozen
procedure was mined only from the four evidence families and frozen before any
held-out call. The runner used `gpt-5.6-luna` through the Codex subscription
harness with gold SQL hidden from the proposer.

## Design

- Held-out families: `card_games`, `formula_1`, and `financial`.
- Two tasks per family, each evaluated in three paired arms: no skill,
  formatting placebo, and trace-mined procedure.
- The independent evaluator used immutable read-only SQLite databases, strict
  ordered result comparison, unordered diagnostic comparison, and bounded
  execution limits.

## Result

| arm | episodes | exact | unordered | mismatches | candidate errors |
|---|---:|---:|---:|---:|---:|
| no skill | 6 | 0 | 0 | 5 | 1 |
| formatting placebo | 6 | 0 | 0 | 5 | 1 |
| trace-mined procedure | 6 | 0 | 0 | 5 | 1 |

All model calls completed through the frontier harness. The candidate arm did
not beat either control, but the cohort is far below the preregistered powered
gate (at least 20 held-out tasks across four families with paired confidence
intervals). The null is therefore typed as `underpowered_pilot`, not
`method_ineffective`; possible contributors include task selection, evaluator
strictness, model output contract, and insufficient task horizon.

No independent causal skill benefit is claimed, no skill is promoted, and no
Frankengate integration is authorized. The next experiment must expand the
family-disjoint cohort and add a separately sealed replay verification of the
episode outcomes before interpreting a method result.
