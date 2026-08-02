# SkillLearnBench task-level paired statistics and receipt audit (2026-08-02)

This audit checks the task-level verifier outcomes behind the SkillLearnBench
skill claims. It also checks whether the later composite receipt's metadata
actually contains a usable answer for every task.

## Three-arm receipt: paired task outcomes

The six-task no-skill, human-authored, and one-shot-generated arms are from one
receipt and share task identities, but they were not randomized in one
simultaneous run.

| arm | q1 fully correct | mean q1 recall | mean q1 precision | q3 fully correct |
| --- | ---: | ---: | ---: | ---: |
| no skill | 2/6 | .8472 | .9667 | 6/6 |
| human-authored | 5/6 | .9444 | 1.0000 | 6/6 |
| one-shot generated | 2/6 | .8843 | 1.0000 | 6/6 |

Task-level q1-full comparisons within that receipt were:

- human-authored versus no-skill: **3 wins, 0 losses, 3 ties**;
- generated versus no-skill: **1 win, 1 loss, 4 ties**.

These are descriptive paired counts, not causal estimates. The sample is one
public task family and q2 has no published gold labels.

## Composite receipt integrity finding

The later file is marked `completed_tasks: 6`, but only **5/6** task records
contain q1 verifier metrics. Task 6 has a status of `completed` with no answer
object. Therefore the published `53/53`, `6/6`, and “all six composite tasks”
claims are not supported by the machine-readable receipt and must be withdrawn.

Among the five answer-bearing composite tasks, q1 is `45/45`, precision `1.0`,
and published-check `5/5`. The sixth task is an operational timeout/missing
answer, not a verified success. A separate-run descriptive join over the six
task IDs gives composite versus no-skill **4 wins/1 loss** and composite versus
human **1 win/1 loss**, but this must not be treated as a randomized comparison.

## Decision

The defensible result is a **5/6 completed composite signal with one missing
task**, not a six-task causal or quality aggregate. Any future composite run
must validate answer presence independently of orchestration metadata and fail
closed when a task is marked complete without verifier output.

Receipt: [paired-statistics and integrity receipt](../results/skilllearnbench-paired-statistics-2026-08-02.json).

