# Quality-filtered State of AI wiki retrieval — 2026-08-02

## Why this second corpus matters

The first State of AI run used the most numerous source domains, including
cache records whose titles were URLs and whose summaries were error pages. That
was useful for measuring metadata preservation, but it was a weak proxy for a
maintained enterprise wiki. This run keeps records with a non-URL title, issuer,
source family, and at least 120 summary characters, excluding
`public_source_cache`.

The result has 400 pages across the ten richest quality-filtered domains and
2,005 deterministic questions: exact title, title paraphrase, issuer/title,
exact identifier, family/title, plus five NIL questions. Each target also has a
nearest same-domain title-token distractor. These are silver labels, not human
review.

## Results at ten domains

| arm | R@1 | R@20 | MRR | NIL false-positive rate |
|---|---:|---:|---:|---:|
| raw BGE | .456 | .946 | .580 | 1.000 |
| compiled BGE | .476 | .951 | .603 | 1.000 |
| identifier reranker over BGE | .695 | .951 | .761 | 1.000 |
| compiled TF-IDF | .599 | .960 | .692 | 1.000 |
| compiled hybrid | .737 | .986 | .798 | 1.000 |
| compiled FTS | **.749** | **.995** | **.807** | 1.000 |

Exact identifier questions were perfect for compiled lexical retrieval. The
paraphrase and issuer/family slices were substantially harder; at ten domains,
compiled hybrid R@1 was .700 for exact titles, .668 for paraphrases, .643 for
issuer/title, .673 for family/title, while identifier queries were 1.000. The
important distinction is that the semantic lane improves candidate recall but
does not replace structured identity fields.

The nearest same-domain distractor appeared in the top 20 about 74% of the time
but displaced the gold result at rank 1 only 3–5% of the time. This is useful
candidate exposure, but it is not yet a validated semantic hard-negative set;
human or frontier review should select genuinely confusable pairs.

## Interpretation

1. Representation dominates backend choice for identity retrieval. Adding
   source IDs, issuer, family, and domain creates a much larger gain than moving
   from general BGE to a dense-only index.
2. The transparent reranker recovers much of the BGE miss rate, but compiled
   FTS remains stronger on this metadata-heavy corpus.
3. NIL handling is independent and currently unsolved. Every arm returns a
   result for all five generated NIL questions. A production agent needs a
   calibrated abstention gate, not a top-k result by default.
4. The next hard-negative step must be reviewed paraphrases and confusable
   same-domain pairs, not more automatically generated title strings.

## Reproducibility

- Adapter: [`stateofai_wiki_quality_adapter.py`](../../stateofai_wiki_quality_adapter.py)
- Generic FTS/TF-IDF/hybrid runner: [`wiki_agentic_rag_benchmark.py`](../../wiki_agentic_rag_benchmark.py)
- Dense runner: [`wiki_dense_benchmark.py`](../../wiki_dense_benchmark.py)
- Identifier reranker: [`wiki_identifier_reranker.py`](../../wiki_identifier_reranker.py)
- Hard-negative audit: [`wiki_hard_negative_audit.py`](../../wiki_hard_negative_audit.py)
- [Content-minimized receipt](../results/stateofai-quality-wiki-retrieval-2026-08-02.json)

No raw source bodies are committed.
