# Governed validated-artifact consumption: four-task paraphrase screen

## Result

Four Defog broker tasks were replayed with their sealed paraphrases under the
same direct Codex/Luna harness, governed PostgreSQL role, authority snapshot,
tool budget, and independent semantic verifier. Each artifact was deliberately
paired with its paraphrase target; no-skill and formatting-placebo controls were
also run.

| Arm | Semantic correctness | SQL attempts | Tool calls |
| --- | ---: | ---: | ---: |
| no-skill | 4/4 | 6 | 14 |
| formatting placebo | 4/4 | 5 | 13 |
| validated artifact | 4/4 | 4 | 12 |

All 12 trajectories were authority-valid and independently recomputed with
zero semantic errors, stored/recomputed mismatches, or policy failures.

## Interpretation

This is stronger than the one-task mechanics smoke: an agent can consume and
submit four validation-carrying SQL artifacts under governed execution, and
the artifact arm used fewer SQL attempts/tool calls in this tiny screen. It
still does **not** demonstrate success or retrieval benefit: every arm reached
`4/4`, and each artifact was paired with the target paraphrase. The attempt
count is descriptive, not a powered cost claim.

The fair next experiment must freeze a train-only artifact library, retrieve
without target pairing, include same-surface wrong-system and true-NIL cases,
and compare reuse with regeneration on larger family/project/schema/time
holdouts plus changed-system replay.

Receipts: [`../results/artifact-reuse-visible-paraphrase-four-task-2026-08-03.json`](../results/artifact-reuse-visible-paraphrase-four-task-2026-08-03.json) and its [verification](../results/artifact-reuse-visible-paraphrase-four-task-2026-08-03-verification.json).
