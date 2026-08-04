# EnterpriseRAG-Bench full source-filter ceiling

Date: 2026-08-10  
Status: completed and independently verified; oracle metadata diagnostic only

## Protocol

This run evaluates all 500 EnterpriseRAG-Bench questions with the same
rare-term OR SQLite FTS5 query as the lexical baseline. It compares:

1. full-corpus lexical retrieval; and
2. an oracle `source_type IN question.source_types` restriction.

The benchmark publishes `source_types` as answer metadata, so the second arm
is an upper bound, not a learned metadata retriever, authorization policy, or
semantic-alias system. The source map and raw documents remain external.

## Full result

| arm | target-bearing MRR | R@1 | R@5 | R@10 | evidence R@10 | wrong-source extras@10 | same-source non-targets@10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| unfiltered | `.511064` | `.444681` | `.591489` | `.646809` | `.584935` | `4.851064` | `4.308511` |
| oracle source-filtered | `.593602` | `.527660` | `.678723` | `.736170` | `.690904` | `0.000000` | `8.963830` |

The filter improved MRR by `.082538`, Recall@1 by `.082979`, and evidence
Recall@10 by `.105969`, while eliminating wrong-source candidates. However,
the remaining irrelevant tail became almost entirely same-source non-targets.
All 30 targetless questions still returned non-empty results in both arms.

## Slice results

The improvement is not uniform:

- semantic MRR `.159632 -> .222425`, evidence R@10 `.248 -> .416`;
- completeness MRR `.6625 -> .83`, evidence R@10 `.43 -> .53625`;
- conflicting-info MRR `.8125 -> .885`, evidence R@10 `.75 -> .90`;
- project-related MRR `.732143 -> .854167`, evidence R@10 `.545486 -> .7375`;
- constrained MRR `.638929 -> .759444`.

This makes the architecture implication concrete: structured source scope is a
high-value first-stage filter, but it does not resolve same-source aliases,
temporal versions, task meaning, or abstention. Those require identifier-aware
ranking, reviewed semantic/NIL labels, and independent replay.

## Claim boundary

This is a document retrieval and hard-negative ceiling measurement. It does
not establish ontology quality, corporate alias correctness, cross-user
learning, skill utility, embedding promotion, or authority safety. The
source-filtered arm must not be confused with RLS or governance enforcement.

## Receipts

- Runner: [`enterprise_rag_source_filter_ceiling.py`](../../enterprise_rag_source_filter_ceiling.py)
- Full receipt: [`enterprise-rag-source-filter-ceiling-2026-08-10.json`](../results/enterprise-rag-source-filter-ceiling-2026-08-10.json)
- Verification: [`enterprise-rag-source-filter-ceiling-verification-2026-08-10.json`](../results/enterprise-rag-source-filter-ceiling-verification-2026-08-10.json)
- Stratified pilot: [`enterprise-rag-source-filter-ceiling-2026-08-10.md`](enterprise-rag-source-filter-ceiling-2026-08-10.md)
