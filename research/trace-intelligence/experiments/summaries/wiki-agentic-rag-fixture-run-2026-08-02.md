# Wiki agentic-RAG fixture run — 2026-08-02

## What was implemented

`wiki_agentic_rag_benchmark.py` now generates a deterministic 25-wiki,
100-page enterprise-shaped fixture and evaluates the same retrieval contract
(`search`, `get_page`, `expand_links`) over SQLite FTS, TF-IDF vectors, and a
hybrid score, using both raw pages and a compiled/interlinked representation.
It reports Recall@1/5, MRR, wrong-wiki rate, NIL false positives, and latency at
1, 5, 10, and 25 wikis. Three unit tests pass.

This is a protocol smoke test, not a Wikipedia benchmark and not a frontier
agent run.

## Raw-page results

The raw hybrid arm is representative of the current baseline:

| wikis | Recall@1 | Recall@5 | MRR | wrong-wiki@1 | NIL false-positive rate | p95 search ms |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | `.750` | `1.000` | `.875` | `.000` | `1.000` | `.276` |
| 5 | `.750` | `1.000` | `.875` | `.000` | `1.000` | `.464` |
| 10 | `.625` | `1.000` | `.812` | `.125` | `1.000` | `.423` |
| 25 | `.550` | `1.000` | `.739` | `.200` | `1.000` | `.767` |

The fixture already exposes two important failure modes:

1. Increasing the wiki count reduces top-1 identity accuracy and increases
   wrong-wiki selection, even though Recall@5 remains perfect.
2. Every NIL query receives a candidate. Retrieval without a calibrated
   abstention/NIL gate is therefore unsafe, even on this small corpus.

Compiled pages did not dominate raw pages: on this fixture, raw hybrid MRR was
`.875/.875/.812/.739` at 1/5/10/25 wikis, while compiled hybrid was
`.708/.833/.771/.698`. This is a fixture result, not evidence against
Karpathy-style compilation; it demonstrates why compiled-vs-raw must be an
explicit arm rather than an assumption.

## Interpretation boundary

The run does **not** establish that FTS, vectors, hybrid search, MCP, or a
compiled wiki is best for real users. The pages and questions are synthetic,
the vector arm is TF-IDF rather than a domain embedding model, and there is no
Claude/Codex agent answering questions. It only validates that the corpus-size,
representation, backend, provenance, and NIL metrics can be produced under a
common contract.

## Next experiment

Add calibrated abstention policies (score threshold, margin, and explicit NIL
classifier), then run the same fixture through a real MCP transport and a
frontier agent. After that, replace the fixture with a licensed Wikipedia
benchmark cohort and a consented enterprise-like wiki with exact identifiers,
aliases, stale facts, and cross-wiki collisions. This is the next phase of
[issue #131](https://github.com/pierretokns/frankengate/issues/131).

## MCP-shaped transport probe

The same hybrid backend was called 100 times directly and through the minimal
stdio JSON-RPC MCP surface. Ranking parity was `1.000`; direct p50/p95 was
`0.562/.784 ms`, while the transport path was `.668/.929 ms`. This isolates a
small local protocol cost, but is deliberately not presented as network MCP or
agent tool-selection evidence.

## Receipts

- [content-minimized result](../results/wiki-agentic-rag-fixture-2026-08-02.json)
- [benchmark implementation](../../wiki_agentic_rag_benchmark.py)
- [receipt generator](../../wiki_agentic_rag_receipt.py)
- [unit tests](../../tests/test_wiki_agentic_rag_benchmark.py)
- [MCP-shaped transport benchmark](../../wiki_mcp_transport_benchmark.py)
