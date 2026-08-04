# SkillLearnBench fit audit (2026-08-05)

The pinned MIT-licensed `cxcscmu/SkillLearnBench` checkout contains:

- 20 tasks and 100 verified instances across 15 sub-domains;
- explicit task verifiers, solution artifacts, and keypoint files for all 20
  tasks;
- four published learning baselines: one-shot, self-feedback,
  teacher-feedback, and skill-creator;
- 25 skill artifact directories (24 model/method combinations plus
  human-authored), each covering all 20 tasks, with 1,277 `SKILL.md` files.

This is a strong adjacent benchmark for continual skill generation. It can
measure task pass rate, skill quality, and trajectory quality, and is useful
for a controlled representation/intervention baseline before Frankengate
claims enterprise transfer.

It does not provide stable enterprise principals, team or tenant identity,
corporate aliases, temporal authority/deletion epochs, changed-system replay,
or cross-user transfer outcomes. Full evaluation also requires model API
credentials and Docker; this audit is static and did not execute those trials.

Receipt:
[`skilllearnbench-fit-audit-2026-08-05.json`](../results/skilllearnbench-fit-audit-2026-08-05.json).

Recommended use: run a frozen no-skill/one-shot/self-feedback/
teacher-feedback/skill-creator subset, then port only the representation or
feedback operator that beats its matched controls into the pre-registered
changed-system Frankengate protocol.

