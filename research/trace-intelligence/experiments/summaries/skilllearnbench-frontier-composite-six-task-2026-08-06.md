# SkillLearnBench composite human + generated skill: six-task replay

Date: 2026-08-06  
Dataset: `cxcscmu/SkillLearnBench`, pinned revision `a0da045a8bf64b8a8ff20730c4d6ef10dc4e2c5b`  
Family: `enterprise-information-search`  
Model: `gpt-5.6-luna` through the Codex subscription

## Result

The prior five-task batch was completed by a separate isolated retry for task
6. The merged receipt contains all six tasks; no answer was imputed.

| arm | q1 correct | q1 recall | q1 precision | published-check passes |
|---|---:|---:|---:|---:|
| null | 43/53 | .811 | .956 | 3/6 |
| one-shot generated | 46/53 | .868 | 1.000 | 2/6 |
| reviewed human | 49/53 | .925 | 1.000 | 5/6 |
| **reviewed + generated composite** | **53/53** | **1.000** | **1.000** | **6/6** |

All six composite tasks also passed the exact q3 verifier. The machine-readable
receipt is [`skilllearnbench-frontier-composite-six-task-2026-08-06.json`](../results/skilllearnbench-frontier-composite-six-task-2026-08-06.json).

## Interpretation

This is stronger than the earlier partial receipt, but it is still not a causal
enterprise result. The composite is one public task family, q2 has no published
gold labels, execution used a host-path portability probe rather than the
official Docker runner, and the arms were not randomized in one simultaneous
run. The composite may be benefiting from additional task-specific context or
procedural coverage rather than a general skill-learning effect.

The result supports a next-stage hypothesis: reviewed procedures and generated
data-navigation procedures may compose without diluting verifier performance.
Promotion still requires a preregistered randomized null/generated/reviewed/
composite/placebo matrix on task-disjoint families, independent q2 labels,
changed-system replay, cost/latency accounting, and negative-transfer gates.
