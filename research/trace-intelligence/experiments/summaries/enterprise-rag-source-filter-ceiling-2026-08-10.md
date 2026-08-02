# EnterpriseRAG-Bench source-filter ceiling pilot

Date: 2026-08-10  
Status: verified pilot; diagnostic only, not a production retrieval result

## Question

How much of the EnterpriseRAG-Bench lexical failure is caused by returning
documents from the wrong source system, and how much remains as same-source
hard negatives? This is a useful bridge to Frankengate's source/authority
metadata and wrong-system negative design.

## Protocol

The pilot selected one deterministic question from each of the ten benchmark
categories. Both arms used the same rare-term OR SQLite FTS5 query as the
lexical baseline and returned ten documents:

1. **Unfiltered:** full-corpus lexical retrieval.
2. **Oracle source-filtered:** `source_type IN question.source_types`.

The second arm is an **oracle ceiling** because the benchmark publishes
`source_types` as answer metadata. It is not a learned alias detector, an
authorization filter, or a fair production comparison. Raw documents and
question text remain external; the receipt stores only aggregate metrics and
question IDs.

## Result (10-question stratified pilot)

| arm | target-bearing MRR | R@1 | R@10 | evidence R@10 | wrong-source extras@10 | same-source non-targets@10 |
|---|---:|---:|---:|---:|---:|---:|
| unfiltered | `.629167` | `.500` | `.875` | `.8125` | `3.375` | `5.375` |
| oracle source-filtered | `.750000` | `.625` | `.875` | `.875` | `0.000` | `8.625` |

The filter removed wrong-source candidates and modestly improved MRR/evidence
recall, but it did **not** reduce the total irrelevant tail: most remaining
items were same-source, non-target documents. This is exactly the hard edge we
need for corporate alias and concept work. Source metadata is necessary but
not sufficient; it cannot decide which document refers to the intended system,
project, temporal version, or task.

Both arms returned non-empty results for the two targetless questions. The
pilot therefore reinforces the existing abstention boundary rather than
solving it.

## Interpretation

This is a small, one-example-per-category ceiling pilot. It does not establish
general benchmark gains, semantic alias quality, ontology correctness, or
artifact/skill utility. It does establish a reproducible design for the next
hard-negative cohort:

```text
source/type scope -> same-source alias and temporal negatives
  -> identifier-aware lexical/dense ranking
  -> NIL/wrong-system adjudication
  -> changed-system replay
```

The full benchmark run is intentionally not promoted from this pilot without
an indexed source-aware corpus and independent semantic labels. A source-type
filter should be treated as a candidate restriction and governance input, not
as the answer to corporate concept discovery.

## Receipts

- Runner: [`enterprise_rag_source_filter_ceiling.py`](../../enterprise_rag_source_filter_ceiling.py)
- Receipt: [`enterprise-rag-source-filter-ceiling-pilot-2026-08-10.json`](../results/enterprise-rag-source-filter-ceiling-pilot-2026-08-10.json)
- Verification: [`enterprise-rag-source-filter-ceiling-pilot-verification-2026-08-10.json`](../results/enterprise-rag-source-filter-ceiling-pilot-verification-2026-08-10.json)
