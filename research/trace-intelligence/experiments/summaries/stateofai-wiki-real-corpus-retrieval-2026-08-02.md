# State of AI wiki real-corpus retrieval — 2026-08-02

## Corpus and labels

The local State of AI wiki export was adapted without committing its raw
content. It contains `3,172` source records; the adapter selected the top 25
source domains, capped at 80 records per domain, yielding `1,281` pages and
`301` deterministic identity queries. Each query's gold label is the source
record whose title/issuer/identifier generated the query. These are retrieval
labels, not human answer-quality labels.

The domain partitions are useful “wiki” scale units, but they are not
independent corporate wikis. This is a real local corpus and a synthetic query
generation protocol.

## Results by corpus size

| arm | 1 domain R@1 / MRR | 5 domains | 10 domains | 25 domains |
|---|---:|---:|---:|---:|
| raw FTS | `.750 / .819` | `.683 / .697` | `.650 / .663` | `.610 / .619` |
| raw TF-IDF | `.667 / .667` | `.667 / .667` | `.642 / .654` | `.567 / .591` |
| raw hybrid | `.750 / .819` | `.683 / .697` | `.650 / .661` | `.607 / .616` |
| compiled FTS | `1.000 / 1.000` | `1.000 / 1.000` | `.933 / .956` | `.947 / .952` |
| compiled TF-IDF | `1.000 / 1.000` | `1.000 / 1.000` | `.967 / .983` | `.863 / .903` |
| compiled BGE-base | `.750 / .836` | `.733 / .821` | `.775 / .846` | `.573 / .666` |

At 25 domains, raw hybrid Recall@20 was `.633`, while compiled FTS was `.967`.
Every arm had a NIL false-positive rate of `1.0` on the generated NIL query
except the smallest TF-IDF cohort. Retrieval scores alone therefore still do
not provide a safe abstention gate.

## Main finding

On this real corpus, adding source IDs, issuer, source family, and domain to a
compiled representation produced a much larger identity-retrieval lift than
switching from lexical/TF-IDF to a general BGE embedding. This is not evidence
that embeddings are useless. It is evidence that exact corporate metadata is
missing from a pure semantic lane and should be preserved as a structured
candidate feature and hard-negative boundary.

The compiled lexical result is also not a fair “Karpathy wiki wins” claim: the
compiled representation explicitly adds identifiers and metadata that raw
documents omit. The correct conclusion is that representation and metadata
must be ablated independently from backend choice.

## Limits

- Queries are generated from titles and metadata; no human questions or answer
  labels are present.
- BGE is a general model, not a corporate-adapted embedding.
- The domain partitions are source-host partitions, not separate enterprise
  wikis.
- No frontier agent, native MCP, citation correctness, stale-fact handling, or
  changed-system outcome was measured here.

## Next experiment

Create reviewed paraphrases, NILs, aliases, and cross-domain hard negatives
for a held-out subset; then compare structured identifier filtering, lexical,
BGE, hybrid, and a domain-adapted reranker. Only after those labels exist can
we connect the real corpus to the frontier wiki loop and enterprise questions.

## Receipts

- [content-minimized receipt](../results/stateofai-wiki-real-corpus-retrieval-2026-08-02.json)
- [State of AI adapter](../../stateofai_wiki_adapter.py)
- [dense benchmark](../../wiki_dense_benchmark.py)
- [receipt generator](../../stateofai_wiki_receipt.py)
