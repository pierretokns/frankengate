# Frontier SkillOpt ALFWorld four-family 35-step checkpoint (2026-07-31)

This is the long-horizon frontier replication intended to close the gap in the
earlier evidence: previous runs covered four families at 12 steps or one task
at 35 steps. This run used four family-disjoint `valid_unseen` tasks whose
environment-provided expert plans were all within the 35-step horizon (12, 6,
34, and 8 steps), and compared no-skill, formatting-placebo, and the published
Microsoft SkillOpt ALFWorld candidate.

## Result

| arm | episodes | steps | Codex calls | wins | win rate | invalid parser actions |
|---|---:|---:|---:|---:|---:|---:|
| no skill | 4 | 140 | 140 | 0 | 0.0 | 0 |
| formatting placebo | 4 | 140 | 140 | 0 | 0.0 | 0 |
| SkillOpt candidate | 4 | 140 | 140 | 0 | 0.0 | 0 |

The candidate had zero paired wins against either control; all four task-level
comparisons tied at zero. A fresh ALFWorld environment replayed all 12 action
sequences with zero receipt mismatches.

## Interpretation

This is a **valid null checkpoint at a sufficient horizon**, not proof that
SkillOpt is ineffective in general. The cohort is only four tasks and the model
did not solve any task in any arm, so semantic utility is unidentifiable beyond
the fact that the candidate did not rescue these tasks. The candidate remains
unreleased and no Frankengate integration is authorized.

The next useful test is not another one-shot prompt comparison: it should
increase the number of expert-solvable tasks and/or test a multi-episode
feedback loop in which a candidate is mined from earlier failures and evaluated
on later tasks with independent replay.

Artifacts:

- Protocol manifest: `../manifests/alfworld-luna-skillopt-four-family-35step-2026-07-31.json`
- Aggregate receipt: `../results/alfworld-luna-skillopt-four-family-35step-2026-07-31.json`
- Replay verification: `../results/alfworld-luna-skillopt-four-family-35step-verification-2026-07-31.json`
- Paired analysis: `../results/alfworld-luna-skillopt-four-family-35step-paired-2026-07-31.json`
