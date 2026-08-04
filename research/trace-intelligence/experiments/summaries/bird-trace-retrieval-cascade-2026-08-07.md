# Outcome-backed retrieval cascade on recorded BIRD traces

## Protocol

This replay uses the 76 independently validated artifacts from the recorded
BIRD trace study. For each target, the candidate pool contains other validated
artifacts from the same database family. Four rankers select candidates:

- question-token lexical overlap;
- SQL identifier overlap (tables and columns parsed structurally);
- cosine similarity over the pinned 512-dimensional `state_action` trace-step
  embeddings shipped with the World Model Harness; and
- a lexical/identifier hybrid.

Every top-1/5/10 candidate is executed against the target database. A match
means only that its result set equals the independently executed gold result;
there are no human intent labels, so result collisions remain possible.

## Results

All four rankers produced the same outcome profile:

| Ranker | Targets | Result match @1 | @5 | @10 | Same normalized template @1/@5 |
|---|---:|---:|---:|---:|---:|
| Lexical | 76 | 0 | 1 | 2 | 0 / 0 |
| Identifier | 76 | 0 | 1 | 2 | 0 / 0 |
| Dense state/action | 76 | 0 | 1 | 2 | 0 / 0 |
| Lexical + identifier | 76 | 0 | 1 | 2 | 0 / 0 |

## Interpretation

On this public cohort, embeddings did not improve executable artifact reuse
over lexical or identifier ranking. That is not a general disproof of dense
retrieval: the validated trace pool contained **zero repeated normalized SQL
templates**, so there was little natural reuse for any ranker to recover. The
result does establish a useful boundary: dense similarity is not an authority
or correctness signal, and adding it to an incompatible artifact pool does not
create reuse.

The architecture remains:

```text
scope / identifiers / authority
  -> compatibility filter
  -> lexical + identifier retrieval
  -> dense candidate expansion (optional)
  -> frontier or human intent review
  -> independent execution / release or refusal
```

The next fair retrieval test needs repeated natural intents, reviewed subplans,
or an authorized enterprise cohort. It should report semantic labels and
changed-system outcomes rather than only result-set collisions.

Receipt: [`bird-trace-retrieval-cascade-2026-08-07.json`](../results/bird-trace-retrieval-cascade-2026-08-07.json).
Independent verification: [`bird-trace-retrieval-cascade-2026-08-07-verification.json`](../results/bird-trace-retrieval-cascade-2026-08-07-verification.json).

