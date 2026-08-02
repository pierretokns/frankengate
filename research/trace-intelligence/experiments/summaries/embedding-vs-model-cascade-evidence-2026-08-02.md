# Embedding versus model cascade: evidence boundary and aligned test

**Status:** public-proxy evidence synthesis; direct interaction not yet tested

## What has actually been measured

| Lane | Cohort and input | Result | What it establishes |
|---|---|---|---|
| Retrieval cascade | 76 independently validated BIRD artifacts, same database-family leave-one-out | Lexical, identifier, dense, and hybrid all matched 0/76 at rank 1, 1/76 at rank 5, and 2/76 at rank 10; none recovered a repeated normalized template | The pool had no natural template reuse. Dense retrieval did not create reuse or authority. |
| Model judgment, prompt-only | 16 balanced BIRD cases | 16/16 valid JSON, but 16/16 abstentions | Prompt text alone was insufficient for artifact judgment under the conservative contract. |
| Model judgment, recorded trajectory | The same 16 cases with the recorded SQL tool call | 7 true positives, 6 false positives, 1 true negative, 2 abstentions; 87.5% recall and 53.8% precision among positive predictions | Tool-call context adds useful signal, but the model is unsafe as an admission gate. |

Receipts: [retrieval cascade](../results/bird-trace-retrieval-cascade-2026-08-07.json),
[model cascade](../results/bird-trace-model-cascade-16-2026-08-08.json).

## The non-combinability finding

These experiments do **not** prove that `dense retrieval -> frontier model`
beats either component. The retrieval study has 76 targets and a natural
reuse/coverage null; the model study has 16 cases and evaluates judgment of a
single recorded artifact. They have different candidate pools, labels, and
task counts. Multiplying their percentages would manufacture a cascade result.

The defensible interpretation is narrower:

1. **Retrieval is a recall/coverage stage.** Exact identifiers and scope are
   safer than dense similarity; dense expansion is optional and cannot confer
   authority.
2. **A frontier model is a selective review stage.** Trajectory context can
   distinguish some correct from incorrect artifacts, but six false positives
   in sixteen cases forbid automatic promotion.
3. **Independent replay is the decision stage.** Neither embedding score nor
   model confidence is a substitute for scope, authority epoch, schema
   compatibility, and changed-system validation.

Thus the architecture can combine the mechanisms sequentially, but their
interaction is still an open empirical question.

## Aligned factorial required before claiming a cascade

Build one task-disjoint cohort of at least 40 reviewed traces with:

- an explicit target artifact, reviewed NIL/unclear cases, and same-surface
  wrong-system negatives;
- source and changed-system environments, authority epoch, and schema version;
- independent terminal replay outcomes; and
- fixed candidate pools so every arm sees the same admissible artifacts.

Run these arms with the same task order, model, and budget:

1. lexical/identifier retrieval only;
2. dense retrieval only;
3. lexical + identifier + dense hybrid;
4. trajectory model on the full admissible pool;
5. retrieval top-*k* followed by trajectory-model review; and
6. retrieval top-*k* followed by human or deterministic review.

Pre-register candidate *k*, abstention rules, and the replay gate. Report:

- Recall@1/5/20 and MRR before review;
- precision, false-accept rate, abstention, and reviewer agreement after review;
- changed-system semantic success and stale/wrong-scope/unauthorized accepts;
- p50/p95 latency, tokens, model calls, and cost per accepted artifact; and
- quality at fixed cost, not quality alone.

The interaction claim is supported only if retrieval+model improves reviewed
semantic success or reduces review cost versus the best single-stage arm,
without increasing unsafe accepts or latency beyond the pre-registered gate.

## Current decision

Keep the cascade in a shadow/review lane. Use exact identifiers and governed
metadata first; use dense retrieval only to widen a bounded candidate set; use a
frontier model to rank or explain candidates; and require deterministic gates
plus independent replay for release. Do not claim embedding-based insight
mining, model-based skill discovery, or combined cascade utility from the two
current public-proxy receipts.
