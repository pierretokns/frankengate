# SkillLearnBench frontier family probe

This is a host-path portability probe, not the upstream Docker benchmark. It
uses `cxcscmu/SkillLearnBench@a0da045a8bf64b8a8ff20730c4d6ef10dc4e2c5b`, the
Codex subscription model `gpt-5.6-luna`, and three held-out instances from the
same `enterprise-information-search` family. The validator reads each task's
pinned `tests/test_outputs.py` rather than reusing task-1 gold IDs.

## Exact results

Each cell is Q1 precision/recall; Q3 was `1.00/1.00` for every arm and task.

| task | no-skill | human-authored skill | skill − no-skill recall |
| --- | ---: | ---: | ---: |
| enterprise-search-2 | `1.00 / .667` | `1.00 / .417` | `-.250` |
| enterprise-search-3 | `1.00 / .875` | `1.00 / 1.00` | `+.125` |
| enterprise-search-4 | `1.00 / .875` | `1.00 / 1.00` | `+.125` |

The macro-average Q1 recall is exactly tied at `.806` in both arms. The
micro-average is `.786` no-skill (22/28 gold IDs) versus `.750` with the skill
(21/28). Thus the skill changes which instances are solved, but produces no
aggregate recall lift and a small negative micro-average on this family. All
returned IDs were exact (precision `1.00`), so this is a recall/coverage issue,
not a wrong-entity hallucination result.

## Interpretation

This is stronger than the single-task portability probe because it has three
held-out instances and task-specific gold sets, but it remains directional:
one task family, one model, one seed, no changed system, no user/project/time
split, no generated-skill or placebo arm, and no upstream Docker runner. It is
therefore not evidence against SkillLearnBench or human-authored skills in
general. It does show that a skill that helps one enterprise-search instance
can hurt another, so promotion must require per-task regression gates and
aggregate outcome tests rather than a single successful replay.

Receipt: [`skilllearnbench-frontier-family-2026-08-05.json`](../results/skilllearnbench-frontier-family-2026-08-05.json).
