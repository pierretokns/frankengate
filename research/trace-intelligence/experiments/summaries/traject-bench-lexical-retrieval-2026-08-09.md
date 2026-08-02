# TRAJECT-Bench lexical retrieval baseline (2026-08-09)

## Protocol

This deterministic arm ranks published tool definitions by Jaccard token
overlap between the query and either the tool name alone or the tool name plus
description. It evaluates set recall against each record's reference tool list
at `k={1,3,5,10,20}`. No model, endpoint, recorded output, or tool execution
was used.

Two candidate-pool policies were measured:

- **Domain pool:** the domain's published `*_tool.json` file.
- **All pool:** the deduplicated 674-name union from `all_tools.json`.

Only records with non-empty reference names that existed in the selected
candidate pool were scored. The run excluded 613/5,910 records: 573 had
missing reference names in the global manifest and 40 had no usable target list.
The domain pool has additional scope-specific omissions. This is a
dataset-coverage issue, not a retrieval failure, and is itself important for
benchmark ingestion.

## Results on the eligible records

| Pool / query type | Arm | Records | MRR | Recall@5 | Recall@20 | Exact set at target-count |
|---|---|---:|---:|---:|---:|---:|
| Domain / parallel hard | name | 1,975 | .6708 | .2822 | .5852 | .0061 |
| Domain / parallel hard | name+description | 1,975 | .5551 | .2288 | .5002 | .0005 |
| Domain / parallel simple | name | 1,987 | .8385 | .4017 | .7614 | .0156 |
| Domain / parallel simple | name+description | 1,987 | .6662 | .3011 | .6680 | .0010 |
| Domain / sequential | name | 1,335 | .7554* | .3691* | .7201* | .0202* |
| All / parallel hard | name | 1,975 | .5585 | .2302 | .4219 | .0076 |
| All / parallel simple | name | 1,987 | .8320 | .4114 | .6919 | .0201 |
| All / sequential | name | 1,335 | .6994* | .3379* | .5932* | .0142* |

`*` is the record-weighted aggregate of the two sequential query-file groups;
the committed receipts retain the uncollapsed groups. Description expansion
hurt the parallel baseline, likely because long tool descriptions introduce
generic vocabulary while queries often contain tool/API names or identifiers.
The broad all-tools pool also hurt recall relative to the domain pool, which is
evidence that scope filtering is useful before semantic retrieval.

## Interpretation

1. Exact/name lexical retrieval is a useful cheap first stage, especially on
   simple queries, but it is far from sufficient for hard or compositional
   queries.
2. Adding descriptions naively is not equivalent to better semantic retrieval;
   it can dilute identifier and tool-name signals.
3. Domain scoping materially improves this baseline compared with a global pool,
   supporting Frankengate's scope-first architecture.
4. The 613 missing target names must be repaired or explicitly excluded before
   a fair model comparison. Otherwise a model can be penalized for candidates
   that the benchmark itself does not publish.

This remains a mechanics baseline. It does not establish that an embedding,
frontier model, LRAT, or ToolQP improves agent success. The next fair arm must
use the same eligible records, fixed cost/latency budgets, and the same target
coverage after repairing the candidate manifest.

Receipts:

- [domain pool](../results/traject-bench-lexical-retrieval-2026-08-09.json)
- [all-tools pool](../results/traject-bench-lexical-retrieval-all-2026-08-09.json)
