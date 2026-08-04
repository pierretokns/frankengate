# SkillLearnBench composite human+generated skill: partial frontier receipt

Date: 2026-08-01  
Dataset: `cxcscmu/SkillLearnBench` (local pinned checkout)  
Arm: reviewed human skill composed with the generated one-shot skill  
Model: `gpt-5.6-luna` through the Codex subscription

## Result

The six-task composite replay was not a complete paired experiment. Five tasks
produced validated answer files; task 6 reached the 900-second frontier timeout
without an answer. The result is therefore an operational receipt, not a quality
aggregate. No composite skill-utility claim is made.

| Measure | Receipt |
|---|---:|
| Tasks scheduled | 6 |
| Tasks with validated answers | 5 |
| Tasks timed out/missing answer | 1 |
| Full paired run | No |
| Composite utility proven | No |
| Enterprise transfer proven | No |

The completed task transcripts remain in the private work directory used by the
runner; raw task content is not committed. The machine-readable receipt is
[`skilllearnbench-frontier-composite-partial-2026-08-01.json`](../results/skilllearnbench-frontier-composite-partial-2026-08-01.json).

## Interpretation

This run establishes a reproducible frontier-cost/timeout boundary for a
composite skill on this host-path adaptation. It does not show that composing
human-reviewed and generated skills improves correctness, nor that the result
transfers to enterprise traces. A fair follow-up must either complete all six
tasks under a pre-registered timeout policy or use a larger task cohort with
matched no-skill, generated-only, reviewed-human, and composite arms.
