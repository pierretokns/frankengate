# TRAJECT-Bench field-aware retrieval probe (2026-08-09)

This probe asks whether preserving structured tool metadata helps cheap lexical
candidate retrieval. It is a retrieval experiment only; it does not measure
embeddings, skill quality, tool execution, or enterprise usefulness.

## Protocol

- Source: the public TRAJECT-Bench `parallel/` and `sequential/` records.
- Scope: domain-local tool pools, so the experiment does not conflate candidate
  generation with cross-domain routing.
- Cohort: 5,297 records whose referenced tools were present in the local pool.
- Arms:
  - `name`: tool-name tokens only.
  - `name_description`: name plus parent/tool descriptions.
  - `field_aware`: weighted name, description, API/domain, parameter schema,
    output metadata, and connected-tool fields.
  - `identifier_schema`: weighted name, API/domain, parameter schema, and output
    metadata.
- The same deterministic tokenization and tie-breaking are used in every arm.

## Result

Weighted averages across 1,975 hard-query records:

| arm | MRR | Recall@1 | Recall@5 | Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| name | 0.670822 | 0.094539 | 0.282150 | 0.421205 |
| name + description | 0.573545 | 0.070274 | 0.238056 | 0.369130 |
| field-aware | 0.631093 | 0.083818 | 0.274042 | 0.423012 |
| identifier + schema | 0.654662 | 0.089420 | 0.268596 | 0.402958 |

The field-aware arm slightly exceeded name-only Recall@10 (`.423012` vs
`.421205`) but lost on MRR and Recall@1. Adding descriptions was consistently
harmful in this benchmark. The identifier/schema arm was also below name-only
on the aggregate hard cohort. Simple queries are easier and show the same
pattern: descriptions reduce retrieval quality, while schema fields provide
small, domain-dependent changes rather than a general win.

## Interpretation

Structured metadata is worth retaining in the canonical trace/tool model, but
this run does not justify a universal field-weighted lexical ranker. Tool names
remain the strongest cheap signal in these benchmark records. The small
Recall@10 improvement from field-aware features is a candidate-generation hint,
not evidence that schemas or embeddings solve aliasing. A corporate follow-up
needs hard wrong-system negatives, renamed identifiers, parameter compatibility,
and outcome labels; otherwise a field ablation can only measure benchmark
string overlap.

The receipt is content-minimized and independently verified. Raw benchmark
files are not committed.

## Receipts

- [machine-readable result](../results/traject-bench-field-retrieval-2026-08-09.json)
- [independent verification](../results/traject-bench-field-retrieval-verification-2026-08-09.json)
- [runner](../../traject_bench_field_retrieval.py)
- [verifier](../../verify_traject_bench_field_retrieval.py)
