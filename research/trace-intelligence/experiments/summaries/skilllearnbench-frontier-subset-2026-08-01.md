# SkillLearnBench frontier portability subset

This is a bounded host-harness probe, not a reproduction of the benchmark's
Docker runner. It uses the pinned MIT-licensed checkout at
`cxcscmu/SkillLearnBench@a0da045a8bf64b8a8ff20730c4d6ef10dc4e2c5b`, one
`enterprise-information-search-1` task, and the Codex subscription model
`gpt-5.6-luna`.

## Result

The no-skill and human-authored arms both produced verifier-valid answers:

| arm | required-key verifier | Q1 exact precision/recall | Q3 exact precision/recall |
| --- | --- | --- | --- |
| no skill | pass | 8/8, 8/8 | 3/3, 3/3 |
| human-authored skill | pass | 8/8, 8/8 | 3/3, 3/3 |

The two arms therefore tie on this task. The skill arm consumed about 171
seconds of wall time; the reused control receipt retained Codex usage but not a
new wall-time measurement. The raw event streams and answer files remain
outside the repository; only hashes and structural receipts are committed.

## Interpretation

This establishes that the pinned SkillLearnBench task and its human-authored
skill can be exercised through the Codex host harness, and that the verifier
can distinguish the required output shape. It does **not** establish skill
utility, causal learning, enterprise transfer, or model superiority: there is
one task, no randomized repeated seeds, no independent changed-system
environment, and the host adapter is not the upstream Docker protocol.

The next valid step is a frozen multi-task subset with no-skill, human-authored,
generated-skill, and placebo arms, exact answer precision/recall (not only
required inclusion), repeated seeds, and an independent verifier. The full
SkillLearnBench runner remains separately gated on its documented provider and
Docker dependencies.

Receipt: [`skilllearnbench-frontier-subset-2026-08-01.json`](../results/skilllearnbench-frontier-subset-2026-08-01.json).
