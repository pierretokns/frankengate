# Governed validated-artifact consumption pilot

## Question

Can an agent consume a previously validated SQL artifact on a semantically
paraphrased question, execute it through governed PostgreSQL, and submit the
same successful attempt without violating authority or policy?

## Protocol

One public Defog broker task was replayed with its sealed paraphrase. Three
arms used the same direct Codex/Luna harness, database, authority snapshot,
tool limits, and independent verifier: no-skill, formatting placebo, and a
validated artifact containing the prior successful SQL. The source artifact
was deliberately paired with this paraphrase, so this is an upper-bound
consumption test—not a retrieval, discovery, or generalization estimate.

## Result

All three arms were semantically correct (`1/1`), used one SQL attempt and
three tool calls, and observed zero unauthorized data. The artifact arm's
execution was independently recomputed against governed PostgreSQL with zero
mismatches or verifier errors.

## Interpretation

This closes a missing mechanics gate: a real frontier agent can consume a
validation-carrying SQL artifact under authority and submit the exact executed
attempt. It does **not** show artifact benefit because both controls also
succeeded, and the source artifact was paired with the target paraphrase.

The next fair test must freeze a library from train-only successful traces,
retrieve without target-task pairing, include negative/NIL candidates, and
measure reuse versus regeneration on larger family-, project-, and
schema-held-out tasks with changed-system replay.

Receipts: [`../results/artifact-reuse-visible-task11-2026-08-03.json`](../results/artifact-reuse-visible-task11-2026-08-03.json) and its [independent verification](../results/artifact-reuse-visible-task11-2026-08-03-verification.json).
