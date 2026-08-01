# Sequential Trace2Skill-style prefix transfer

## Protocol

This run adapts the sequential spirit of SkillLearnBench and SkillFlow. A
Trace2Skill-style compiler saw only six source JSONL files: two task histories,
each represented by no-skill, placebo, and trace-mined arms. It then compiled a
candidate procedure without seeing the two replay task IDs. The candidate was
replayed on those different task IDs under a fresh native Codex/Postgres run.

Each arm received a fresh Postgres container, governed role, port, raw-audit
root, and independent semantic verifier. The controls were no-skill and a
length-matched neutral prompt.

## Result

| Arm | Semantic correct | Rate | SQL attempts | Unauthorized observations |
|---|---:|---:|---:|---:|
| no skill | 2/2 | 1.00 | 3 | 0 |
| length-matched neutral | 1/2 | 0.50 | 2 | 0 |
| prefix-compiled procedure | 2/2 | 1.00 | 4 | 0 |

The compiled procedure tied no-skill on both held-out tasks and beat the
neutral control on one of two paired episodes. Exact paired McNemar p=1.0.
Independent semantic recomputation passed for all six episodes; authority was
valid for all six and unauthorized observations were zero.

## Interpretation

This is evidence of **transferability**, not evidence of incremental utility:
the procedure compiled from a small prefix did not collapse on new tasks, but
it did not beat the no-skill agent. It also used more SQL attempts/tool calls
than no-skill (4 versus 3), so the current sample does not support an
efficiency claim.

The result reinforces the literature's distinction between skill quality,
trajectory quality, and changed-task outcome. A candidate can be well-grounded
and transferable while adding no measurable success benefit. Promotion remains
false until a larger sequential cohort shows lift over both no-skill and
neutral controls, including negative-transfer families and cost/latency gates.

## Receipts

* Prefix candidate: `experiments/results/trace2skill-defog-sequential-prefix2-candidate-2026-08-02.json`
* Merged replay: `experiments/results/defog-codex-frontier-native-sequential-prefix2-seed-530000-merged-2026-08-02.json`
* Independent verification: `experiments/results/defog-codex-frontier-native-sequential-prefix2-seed-530000-merged-independent-verification-2026-08-02.json`
* Aggregate: `experiments/results/trace2skill-sequential-prefix2-seed-530000-aggregate-2026-08-02.json`

Raw trajectories remain outside the repository.
