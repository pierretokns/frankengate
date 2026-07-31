# Frontier-generated durable memory on ALFWorld (four-family, 35-step)

A frontier model distilled a bounded procedural memory from a separate
valid-seen expert episode (5 expert steps). The held-out valid-unseen agent did
not see the source trace, expert plan, or future outcomes. It was compared with
no-memory and formatting-placebo controls on four family-disjoint tasks, each
with a 35-step horizon.

| arm | episodes | wins | win rate | invalid decisions | steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| no memory | 4 | 0 | 0.00 | 1 | 140 |
| formatting placebo | 4 | 0 | 0.00 | 0 | 140 |
| generated memory | 4 | 0 | 0.00 | 0 | 140 |

Generated memory tied both controls on all four paired tasks. The one
no-memory invalid decision was caused by a failed frontier call and fell back
to an admissible action; the generated-memory arm had no invalid decisions.
The fresh-environment verifier passed all 12 rows with zero mismatches and zero
inadmissible executed actions.

This is a valid small null for this memory release: it produced no success
lift, although it did not worsen protocol validity. It does not establish that
durable memory, Graphiti, LangMem, or memory extraction in general is useless;
the memory source and target are small and the model solved none of the tasks.
Automatic memory promotion remains blocked pending larger disjoint cohorts,
repeated seeds, and a task set where the no-memory control has measurable
headroom.

Receipts:

- `experiments/results/alfworld-luna-generated-memory-four-family-35step-2026-07-31.json`
- `experiments/results/alfworld-luna-generated-memory-four-family-35step-verification-2026-07-31.json`
- `experiments/results/alfworld-luna-generated-memory-four-family-35step-paired-2026-07-31.json`
- `experiments/manifests/alfworld-luna-generated-memory-four-family-35step-2026-07-31.json`
