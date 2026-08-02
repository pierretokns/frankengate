# SkillLearnBench changed-data multi-seed synthesis (2026-08-09)

The same public changed-data task was run twice through the Codex/Luna
frontier harness: once on 2026-08-01 and once on 2026-08-06. This is a
seed-stability diagnostic, not a two-task benchmark. The mutation renamed
`ContentForce` to `ContentHub` in the prompt and data while keeping the
published verifier and expected IDs unchanged.

## Aggregate q1 result

| Arm | Correct IDs | Expected IDs | False positives | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| Null | 15/16 | 16 | 1 | .938 | .938 |
| Reviewed human guidance | 16/16 | 16 | 0 | 1.000 | 1.000 |
| Human + generated composite | 15/16 | 16 | 0 | .938 | 1.000 |

All arms returned the exact q3 answer in both runs (`2/2` each). The reviewed
guidance arm was the only arm stable at full q1 precision and recall across
both frontier runs. The composite arm was perfect in the first run but missed
one expected ID in the second; generated composition therefore added no
demonstrated value and introduced a stability risk on this task.

## Interpretation

This strengthens the earlier one-task observation but does not turn it into a
skill-learning claim. Both runs use the same task, same public fixture, and
same renamed product; repeated seeds are not independent task evidence. The
result supports a practical ordering for future studies:

1. test reviewed, human-readable guidance under changed names/data;
2. measure generated/composed guidance as a separate arm; and
3. require task-disjoint changed fixtures, regression labels, and independent
   outcomes before promoting generated skills.

The result is consistent with the broader BIRD nulls: generic trace-mined
prose and automatic composition are not promotion-ready, while validated or
reviewed artifacts remain plausible bounded candidates.

## Receipt

- [aggregate receipt](../results/skilllearnbench-changed-data-multiseed-2026-08-09.json)
- [2026-08-01 source run](../results/skilllearnbench-changed-data-frontier-2026-08-01.json)
- [2026-08-06 source run](../results/skilllearnbench-changed-data-frontier-2026-08-06.json)

