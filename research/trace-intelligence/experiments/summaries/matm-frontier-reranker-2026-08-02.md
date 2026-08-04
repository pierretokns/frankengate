# Frontier-model reranking on MATM trace candidates

## Question

After exact/lexical and dense candidate generation, does a frontier model add
useful ranking signal for finding related traces?

## Protocol

The run used the pinned `toeunkim/matm-trajectories` revision with 2,130
trajectories from 34 models. Nine leave-one-model-out queries were selected.
The candidate pool was the union of lexical top candidates, cached-embedding
top candidates, and all candidates sharing the silver normalized
`task_type + goal` signature. Luna saw only compact goal/action summaries and
was not shown success labels or task IDs. Lexical, embedding, and Luna orders
were scored against the same silver signature labels.

Receipt: [`../results/matm-frontier-reranker-luna-9q-2026-08-02.json`](../results/matm-frontier-reranker-luna-9q-2026-08-02.json).
Independent verification receipt: [`../results/matm-frontier-reranker-luna-9q-verification-2026-08-02.json`](../results/matm-frontier-reranker-luna-9q-verification-2026-08-02.json).
Raw prompts and model responses remain external under
`/private/tmp/matm-frontier-reranker-20260802/`.

## Result

| Ranker | MRR | Recall@1 | Recall@3 | Recall@5 | Top-3 success rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| lexical | 1.000 | 1.000 | 1.000 | 1.000 | .704 |
| frontier Luna | 1.000 | 1.000 | 1.000 | 1.000 | .704 |
| cached embedding | .674 | .556 | .778 | 1.000 | .667 |

All nine frontier calls returned valid structured output; no calls failed.

## Interpretation

This is a **null incremental reranker result**, not a model-quality defeat:

- Luna did not improve over lexical ranking on this candidate pool.
- The pool construction guarantees that many silver-positive candidates are
  present, so this does not test candidate recall or hidden semantic aliases.
- The silver label is the same normalized goal signature across models, not a
  human judgment of transferable procedure, enterprise identity, or outcome.
- Latency and dollar cost were not measured in this receipt; frontier ranking
  is necessarily the more expensive stage.

The result supports the current cascade: exact/structured/lexical retrieval
should do the cheap first pass; a frontier model should be reserved for
ambiguous, high-value, human-review cases or for adjudicating hard negatives.
It should not be inserted into every retrieval request by default.

## Required follow-up

Run a blinded hard-negative set containing same-surface/different-system,
temporal-neighbor, tool-schema-conflict, and NIL cases. Freeze candidate
generation before ranking, collect SME labels and abstentions, and measure
quality per dollar/latency. Only then test whether a reranker changes artifact
selection or downstream replay outcomes.

This receipt does not establish semantic trace similarity, user-pattern
discovery, skill utility, or enterprise transfer.
