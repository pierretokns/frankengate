# SkillLearnBench frontier family replay (2026-08-01)

Three held-out instances from the same `enterprise-information-search` task
family were replayed with the Codex subscription (`gpt-5.6-luna`) using the
same host-path adaptation as the one-task probe. Each instance had a no-skill
arm and the human-authored `artifact-review-search` arm. The published q1/q3
gold lists were parsed from each instance's verifier; q2 remains unlabeled.

| instance | arm | q1 precision | q1 recall | q3 precision/recall | verifier pass |
|---|---|---:|---:|---:|---:|
| 1 | no skill | `.800` | `1.000` | `1.000 / 1.000` | yes |
| 1 | human skill | `1.000` | `1.000` | `1.000 / 1.000` | yes |
| 2 | no skill | `1.000` | `.333` | `1.000 / 1.000` | no |
| 2 | human skill | `1.000` | `.667` | `1.000 / 1.000` | no |
| 3 | no skill | `1.000` | `.875` | `1.000 / 1.000` | no |
| 3 | human skill | `1.000` | `1.000` | `1.000 / 1.000` | yes |

Micro-averaged over the published q1 gold sets, the skill arm improved recall
from `19/28 = .679` to `24/28 = .857` and precision from `19/21 = .905` to
`24/24 = 1.000`. The q3 answers were exact in all six arms. Published-check
pass rate improved from `1/3` to `2/3`.

The result is stronger than the original one-instance signal: the procedure
removed false positives on instance 1 and recovered additional IDs on
instances 2 and 3. It is still not a causal skill-learning result. All three
tasks are one public family, q2 has no gold label, the runner is a host-path
adaptation rather than the official Docker runner, and no changed-system or
cross-user outcome is measured.

The human-skill arm used `3,405,876` input tokens versus `2,094,657` for the
null arm (about `1.63x`) and `24,505` output tokens versus `19,314` (about
`1.27x`). Quality and cost must therefore be gated together.

Receipt:
[`skilllearnbench-frontier-family-2026-08-01.json`](../results/skilllearnbench-frontier-family-2026-08-01.json)

Raw data, answers, and Codex event logs remain in disposable `/private/tmp`
directories and are not committed.
