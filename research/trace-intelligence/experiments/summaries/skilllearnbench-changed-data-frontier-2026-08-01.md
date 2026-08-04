# Changed-data SkillLearnBench frontier replay (2026-08-01)

This is a public changed-environment proxy, not an enterprise cohort. In the
first `enterprise-information-search` instance, every occurrence of
`ContentForce` in the prompt and data was renamed to `ContentHub`, including
the product filename. Published answer IDs and the verifier were unchanged.
The same Codex/Luna host adapter then ran null, reviewed human, and composite
reviewed-plus-generated arms.

| arm | q1 recall | q1 precision | q3 exact | task pass |
|---|---:|---:|---:|---:|
| null | `.875` (7/8) | `1.000` | `1.000` | no |
| reviewed human | `1.000` (8/8) | `1.000` | `1.000` | yes |
| composite human + generated | `1.000` (8/8) | `1.000` | `1.000` | yes |

The rename caused the null arm to miss one expected reviewer ID, while both
skill-bearing arms remained exact. This is a useful robustness signal for the
procedures, but it is not evidence of causal skill improvement: one public
task, one deterministic rename, no user identity, no independent human
outcome, and no official Docker runner. It also does not prove that the
generated components contributed beyond the reviewed procedure.

Recorded input/output tokens were 398,532/4,388 (null), 1,048,210/8,189
(reviewed), and 522,562/6,932 (composite). These are execution receipts, not
cost estimates.

Receipt: [`skilllearnbench-changed-data-frontier-2026-08-01.json`](../results/skilllearnbench-changed-data-frontier-2026-08-01.json)

Runner: [`skilllearnbench_changed_data_frontier.py`](../../skilllearnbench_changed_data_frontier.py)
