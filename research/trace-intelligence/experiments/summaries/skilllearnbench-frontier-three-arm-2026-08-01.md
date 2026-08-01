# Three-arm SkillLearnBench enterprise-search replay (2026-08-01)

The complete six-instance enterprise-search family was replayed with three
arms under the Codex subscription (`gpt-5.6-luna`): no skill, the human-authored
`artifact-review-search` procedure, and the published one-shot generated skill
(`b1-one-shot-claude-sonnet-4-6`). All arms used the same task-specific q1/q3
gold lists; q2 remains unlabeled.

| aggregate | no skill | one-shot generated skill | human-authored skill |
|---|---:|---:|---:|
| q1 correct IDs | 43/53 | 46/53 | 49/53 |
| q1 recall | `.811` | `.868` | `.925` |
| q1 precision | `.956` | `1.000` | `1.000` |
| q1 false positives | 2 | 0 | 0 |
| q3 exact arms | 6/6 | 6/6 | 6/6 |
| published-check pass rate | 3/6 | 2/6 | 5/6 |

The generated skill removed the null arm's false positives and improved q1
recall, but it was materially weaker than the human-authored procedure and
actually passed fewer complete task instances than null because it missed one
or more IDs on several tasks. It was not uniformly bad: it matched the human
arm on tasks 2, 3, and 6, but underperformed it on tasks 1, 4, and 5.

The human arm used `6,594,279` input tokens; the generated arm used `2,859,185`
and the null arm `3,755,386`. The generated artifact is therefore cheaper in
this run, but its lower recall makes “skill exists” an inadequate promotion
criterion. Both skill arms had zero observed false positives, so the next
experiment should separate precision safety from recall completeness and test
whether generated skills can be reviewed or composed with the human procedure.

This remains directional public-proxy evidence: one task family, incomplete
question labels, host-harness adaptation rather than official Docker, and no
changed-system or user outcome. It does not prove trace-mined skill utility in
an enterprise.

Receipt:
[`skilllearnbench-frontier-family-three-arm-2026-08-01.json`](../results/skilllearnbench-frontier-family-three-arm-2026-08-01.json)
