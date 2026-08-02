# SSL representation crosswalk for corporate traces (2026-08-02)

This note separates the published SSL result from what has actually been
tested on traces. SSL here means **Scheduling--Structural--Logical**, not
self-supervised learning. The source paper reports skill-registry results on
6,184 public skills and 431 discovery queries; it is adjacent to, but not a
trace-learning experiment.

## What the source establishes

The paper's normalized skill graph has three layers:

| SSL layer | Purpose in the paper | Frankengate analogue |
| --- | --- | --- |
| Scheduling | capability/interface fingerprint, supported intents, contracts, dependencies, operator/status | request intent, principal/project scope, tool/model trigger, authority and temporal window |
| Structural | scenes and transitions such as preparation, acquisition, reasoning, action, verification, recovery | span/step DAG, tool dependencies, retries, branches, phase boundaries and first-fault/recovery edges |
| Logical | grounded atomic actions, resource use, effects, and typed action primitives | typed tool calls, parameter/schema identifiers, read/call/write/check effects, validator and execution outcomes |

The paper reports MRR@50 of `.649` for a short-description baseline and `.729`
for its richest SSL view, with a bootstrap confidence interval for the
difference of `[.051, .111]`. Its risk-assessment macro-F1 rises from `.409`
to `.509`. The normalization process is LLM-mediated and the authors' audit
found grounding issues in 17% of sampled outputs. These are useful evidence
that disentangling interface, execution structure, and resource effects can
help a skill registry; they are not evidence of corporate trace transfer.

## What our trace proxy actually tested

The existing TRAJECT-Bench field-aware probe is the closest empirical test in
this repository. It used 5,297 domain-scoped tool records and compared names,
descriptions, API/domain fields, parameter schemas, output metadata, and
connected-tool metadata over 1,975 hard queries:

| arm | MRR | Recall@1 | Recall@10 |
| --- | ---: | ---: | ---: |
| name only | `.670822` | `.094539` | `.421205` |
| name + description | `.573545` | `.070274` | `.369130` |
| field-aware metadata | `.631093` | `.083818` | `.423012` |
| identifier + schema | `.654662` | `.089420` | `.402958` |

This is not an SSL reproduction: the public benchmark has tool metadata and
target tool lists, but no grounded scene graph, logical effects, enterprise
aliases, authority decisions, or independently verified outcomes. Still, it
gives a useful lower-bound warning. Retaining structured fields produced only
a small Recall@10 change and descriptions were harmful; the fields did not
replace exact names or provide semantic alias discovery.

## Decision for Frankengate

Adopt the **data model idea**, not an unvalidated SSL normalizer or a new
database:

1. Preserve a loss-aware trace DAG and derive scheduling, structural, and
logical projections from the same event IDs.
2. Keep exact identifiers, scope, authority, parameters, effects, and
   independent execution results as first-class fields; do not flatten them
   into an embedding-only document.
3. Treat LLM normalization as a review proposal. It may suggest scenes or
   action types, but it cannot grant authority, mark an artifact valid, or
   publish a skill.
4. Measure the real SSL hypothesis only on a consented skill/trace cohort with
   repeated intents, reviewed aliases, same-surface wrong-system negatives,
   temporal changes, and replayable outcomes. Compare flat text, a
   length-matched outline, structured projections, and structured-plus-text
   under the same candidate pool and cost budget.

## Current claim boundary

The source paper is a positive prior for structured disentanglement in skill
discovery and risk review. Our own evidence supports preserving structured
trace fields, but does **not** yet show better corporate artifact retrieval,
skill improvement, cross-user recommendations, or employee skill-gap
identification. The decisive missing experiment is a held-out enterprise
cohort where the logical layer contains validated effects and replay outcomes;
without that, an SSL-shaped representation could merely encode benchmark
string overlap.

## Sources and receipts

- [SSL research synthesis](/Users/pierre/consulting/stateofai/research/21-benchmarks/ssl-financial-representation-2026.md)
- [TRAJECT-Bench field-aware retrieval](traject-bench-field-retrieval-2026-08-09.md)
- [TRAJECT-Bench field-aware result](../results/traject-bench-field-retrieval-2026-08-09.json)
- [Current research-program status](research-program-status-2026-08-09.md)
