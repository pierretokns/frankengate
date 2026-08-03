# A-RAG hierarchical retrieval reproduction (2026-08-03)

## Question

Does exposing keyword search, semantic search, and bounded chunk reads as
separate tools improve a frontier agent's retrieval and answer behavior over
the existing fixed hybrid `search`/`get_page` contract as the number of wikis
increases?

The design is adapted from [A-RAG](https://arxiv.org/abs/2602.03442), whose
central claim is that the model should participate in retrieval decisions
through hierarchical interfaces rather than receive one opaque top-k context.
This is a bounded reproduction, not a claim that the paper was fully
reproduced.

## Protocol

- Same deterministic 25-wiki/100-page enterprise-shaped fixture as the earlier
  frontier baseline; same 1, 5, 10, and 25-wiki scales and five cases per scale
  (four target questions plus one NIL question).
- Same Codex CLI structured-action harness and `gpt-5.6-luna` model.
- A-RAG tools: `keyword_search` (SQLite FTS), `semantic_search` (TF-IDF), and
  `read_chunk` (at most 320 characters). The model chooses one action per turn,
  with a five-step limit.
- Evaluator-only gold page IDs; the model receives no gold labels or target
  answer. The receipt is content-minimized; no real-user trace is involved.
- Native MCP was not used because the existing non-interactive Codex setup
  cancels custom MCP calls before `tools/call` dispatch.

## Results

| wikis | A-RAG target accuracy | fixed-hybrid target accuracy | A-RAG searched gold | A-RAG loaded gold | A-RAG avg steps | A-RAG p95 wall ms | A-RAG errors |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `1.00` | `1.00` | `1.00` | `1.00` | `3.0` | `31,653` | `0/5` |
| 5 | `1.00` | `1.00` | `1.00` | `1.00` | `3.2` | `28,703` | `0/5` |
| 10 | `1.00` | `1.00` | `1.00` | `1.00` | `3.2` | `37,149` | `0/5` |
| 25 | `0.75` | `0.75` | `1.00` | `1.00` | `3.6` | `50,739` | `1/5` |

The fixed-hybrid comparison is the earlier receipt
[`wiki-frontier-codex-loop-2026-08-02.json`](../results/wiki-frontier-codex-loop-2026-08-02.json).
The A-RAG run is [`wiki-arag-codex-receipt-2026-08-03.json`](../results/wiki-arag-codex-receipt-2026-08-03.json).

The agent mostly selected `keyword_search` (24 calls), with only six
`semantic_search` calls across all 20 cases. It used `read_chunk` 16 times.
The one 25-wiki failure was the cross-wiki disambiguation case: it found the
gold page but exhausted the five-step budget before producing an answer.

## Interpretation

This reproduction does **not** show an accuracy gain from A-RAG on this
fixture. At 25 wikis it reproduces the baseline's `0.75` answer accuracy and
one failed case, while its p95 wall-clock time is higher. The result is not a
disproof of A-RAG: the fixture is identifier-heavy, only 20 cases, semantic
search is TF-IDF rather than a neural retriever, and the baseline and A-RAG
runs are separate stochastic frontier runs. It does show that merely exposing
three tools is insufficient; the agent must learn when semantic retrieval and
fine-grained reading are worth their extra turns.

The most useful enterprise implication is a **conditional** one: A-RAG is a
candidate control policy for mixed identifier/paraphrase/long-document
queries, not a default replacement for exact/scope retrieval. The next fair
test must stratify questions by identifier, alias, paraphrase, multi-hop link,
stale/temporal fact, and NIL; hold the question IDs and model seed fixed; and
charge every tool call against an explicit token/latency budget.

## Next gate

1. Add balanced semantic, multi-hop, temporal-rename, and NIL cohorts.
2. Compare fixed hybrid, A-RAG tool choice, and an oracle tool-choice upper
   bound on identical questions.
3. Add calibrated abstention and wrong-wiki/temporal-collision metrics.
4. Only then combine A-RAG with LRAT exposure supervision, AgentTrails
   provenance, or DQA diagnostic state. A combined stack would otherwise hide
   whether the retrieval interface itself helps.

## Implementation and tests

- [`wiki_arag_codex_loop.py`](../../wiki_arag_codex_loop.py)
- [`wiki_arag_receipt.py`](../../wiki_arag_receipt.py)
- [`tests/test_wiki_arag_codex_loop.py`](../../tests/test_wiki_arag_codex_loop.py)
- Seven contract tests pass with `uv run pytest -q tests/test_wiki_arag_codex_loop.py tests/test_wiki_agentic_rag_benchmark.py`.
