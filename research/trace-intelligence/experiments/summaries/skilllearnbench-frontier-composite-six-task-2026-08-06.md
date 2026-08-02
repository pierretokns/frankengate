# SkillLearnBench composite human + generated skill: six-task schedule audit

Date: 2026-08-06  
Dataset: `cxcscmu/SkillLearnBench`, pinned revision `a0da045a8bf64b8a8ff20730c4d6ef10dc4e2c5b`  
Family: `enterprise-information-search`  
Model: `gpt-5.6-luna` through the Codex subscription

## Result

The prior five-task batch was followed by a separate task-6 retry, but the
machine-readable merged receipt is internally inconsistent: it marks six tasks
as completed while task 6 has no answer or q1/q3 verifier metrics. No answer is
imputed here; task 6 is treated as missing.

| arm | q1 correct | q1 recall | q1 precision | published-check passes |
|---|---:|---:|---:|---:|
| null | 43/53 | .811 | .956 | 3/6 |
| one-shot generated | 46/53 | .868 | 1.000 | 2/6 |
| reviewed human | 49/53 | .925 | 1.000 | 5/6 |
| **reviewed + generated composite** | **45/45 on 5 answer-bearing tasks** | **1.000** | **1.000** | **5/5** |

Five composite tasks passed the exact q3 verifier; task 6 has no verifier
answer. The machine-readable receipt is
[`skilllearnbench-frontier-composite-six-task-2026-08-06.json`](../results/skilllearnbench-frontier-composite-six-task-2026-08-06.json),
and the independent integrity audit is
[`skilllearnbench-paired-statistics-2026-08-02.json`](../results/skilllearnbench-paired-statistics-2026-08-02.json).

## Interpretation

This is a five-task completed signal with one missing task, not a six-task
quality aggregate or causal enterprise result. The composite is one public
task family, q2 has no published gold labels, execution used a host-path
portability probe rather than the official Docker runner, and the arms were
not randomized in one simultaneous run. The composite may be benefiting from
additional task-specific context or procedural coverage rather than a general
skill-learning effect.

The result supports a next-stage hypothesis: reviewed procedures and generated
data-navigation procedures may compose without diluting verifier performance.
Promotion still requires a preregistered randomized null/generated/reviewed/
composite/placebo matrix on task-disjoint families, independent q2 labels,
changed-system replay, cost/latency accounting, and negative-transfer gates.
