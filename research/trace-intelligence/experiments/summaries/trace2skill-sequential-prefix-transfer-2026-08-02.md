# Sequential Trace2Skill-style prefix transfer: contamination correction

## Protocol

This run was intended to adapt the sequential spirit of SkillLearnBench and
SkillFlow. A later raw-audit check showed that the six source JSONL files and
the two replay task IDs were not disjoint: both source and replay included
broker tasks `2` and `11`. The apparent 2/2 prefix result is therefore
**contaminated** and cannot support held-out transfer. It remains a useful
receipt of sequential/compiler plumbing only.

Each arm received a fresh Postgres container, governed role, port, raw-audit
root, and independent semantic verifier. The controls were no-skill and a
length-matched neutral prompt.

## Result

| Arm | Semantic correct | Rate | SQL attempts | Unauthorized observations |
|---|---:|---:|---:|---:|
| no skill | 2/2 | 1.00 | 3 | 0 |
| length-matched neutral | 1/2 | 0.50 | 2 | 0 |
| prefix-compiled procedure | 2/2 | 1.00 | 4 | 0 |

The contaminated compiled procedure tied no-skill on both episodes and beat the
neutral control on one. Exact paired McNemar p=1.0.
Independent semantic recomputation passed for all six episodes; authority was
valid for all six and unauthorized observations were zero.

## Interpretation

This is not evidence of transferability because of source/replay overlap. It
does not support incremental utility or efficiency: the compiled arm used more
SQL attempts/tool calls than no-skill (4 versus 3).

The result reinforces the literature's distinction between skill quality,
trajectory quality, and changed-task outcome. A candidate can be well-grounded
and transferable while adding no measurable success benefit. Promotion remains
false until a genuinely disjoint sequential cohort shows lift over both
no-skill and neutral controls, including negative-transfer families and
cost/latency gates. The corrected disjoint car-to-broker replay is the
authoritative null result for this compiler family.

## Receipts

* Prefix candidate: `experiments/results/trace2skill-defog-sequential-prefix2-candidate-2026-08-02.json`
* Merged replay: `experiments/results/defog-codex-frontier-native-sequential-prefix2-seed-530000-merged-2026-08-02.json`
* Independent verification: `experiments/results/defog-codex-frontier-native-sequential-prefix2-seed-530000-merged-independent-verification-2026-08-02.json`
* Aggregate: `experiments/results/trace2skill-sequential-prefix2-seed-530000-aggregate-2026-08-02.json`

Raw trajectories remain outside the repository.
