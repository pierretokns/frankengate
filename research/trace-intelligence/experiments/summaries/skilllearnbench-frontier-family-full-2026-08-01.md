# Complete SkillLearnBench enterprise-search family replay (2026-08-01)

All six public `enterprise-information-search` instances were replayed with
the same Codex subscription model (`gpt-5.6-luna`) in two arms: no skill and
the human-authored `artifact-review-search` procedure. The host-path runner
used the same task data and task-specific q1/q3 gold lists for both arms. q2
remains unlabeled in the benchmark.

| aggregate | no skill | human-authored skill |
|---|---:|---:|
| q1 expected IDs | 53 | 53 |
| q1 correct IDs | 43 (`.811` recall) | 49 (`.925` recall) |
| q1 returned IDs | 45 | 49 |
| q1 precision | `.956` | `1.000` |
| q1 false positives | 2 | 0 |
| q3 exact arms | 6/6 | 6/6 |
| published-check pass rate | 3/6 | 5/6 |

Per-instance q1 recall was:

| instance | no skill | human skill |
|---:|---:|---:|
| 1 | `1.000` | `1.000` |
| 2 | `.333` | `.667` |
| 3 | `.875` | `1.000` |
| 4 | `.875` | `1.000` |
| 5 | `1.000` | `1.000` |
| 6 | `1.000` | `1.000` |

The reviewed procedure improved four instances, tied two, introduced no
observed false positives, and produced no observed regression. This is much
stronger than the original one-instance signal, but it is still directional:
all tasks come from one public family, q2 has no gold labels, the run uses a
host-path portability adaptation rather than the official Docker runner, and
there are no changed-system, user, or cross-user outcomes.

The human arm consumed `6,594,279` input tokens versus `3,755,386` for null
(about `1.76x`) and `45,052` output tokens versus `33,687` (about `1.34x`).
Any production promotion must therefore include a cost/latency gate.

Receipt:
[`skilllearnbench-frontier-family-full-2026-08-01.json`](../results/skilllearnbench-frontier-family-full-2026-08-01.json)

Raw data, answers, and Codex event logs remain outside the repository in
disposable `/private/tmp` directories.
