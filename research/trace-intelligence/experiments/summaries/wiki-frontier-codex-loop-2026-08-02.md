# Codex/Luna frontier wiki loop — 2026-08-02

## Protocol

This run uses `gpt-5.6-luna` through the Codex CLI subscription. Because the
non-interactive Codex MCP client cancelled custom `tools/call` requests before
dispatch, the model emitted a strict JSON action (`search`, `get_page`,
`expand_links`, or `finish`) and the runner executed that action against the
same wiki contract. Native MCP behavior is therefore not being claimed here;
the test isolates frontier-agent incorporation and reasoning over retrieved
pages.

There were five questions at each corpus size: exact identifier, semantic
paraphrase, alias, cross-wiki disambiguation, and NIL/not-found. Twenty cases
ran across 1, 5, 10, and 25 wikis, with a five-step limit.

## Results

| wikis | target answer accuracy | gold page searched | gold page loaded | NIL abstention | finished | errors | p95 latency |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `1.00` | `1.00` | `1.00` | `1.00` | `1.00` | `0` | `38.3 s` |
| 5 | `1.00` | `1.00` | `1.00` | `1.00` | `1.00` | `0` | `33.2 s` |
| 10 | `1.00` | `1.00` | `1.00` | `1.00` | `1.00` | `0` | `34.3 s` |
| 25 | `.75` | `1.00` | `1.00` | `1.00` | `.80` | `1` | `39.4 s` |

At 25 wikis, the agent still retrieved and loaded the correct page on every
target case, but one cross-wiki disambiguation task exhausted the step limit
before producing an answer. This is an incorporation/decision saturation
signal, not a candidate-recall failure. The NIL cases all abstained correctly,
although some first inspected an irrelevant candidate before refusing.

## Interpretation

- A frontier agent can use the contract successfully at small scale when the
  correct page is available.
- Corpus growth exposed a failure even with perfect gold-page retrieval: tool
  selection and answer completion can saturate before retrieval Recall@k does.
- The synthetic fixture is intentionally easy and small. The result does not
  establish performance on Wikipedia, enterprise wikis, real MCP networking,
  Claude Code, or corporate traces.
- The latency is end-to-end Codex invocation latency, not backend search
  latency. The local direct/MCP-shaped backend overhead remains sub-millisecond
  in the separate transport probe.

## Next controlled comparison

Repeat this loop with (a) raw filesystem search, (b) native MCP after an
interactive approval path is available, (c) the same MCP server backed by FTS,
TF-IDF, and a real embedding model, and (d) a compiled Karpathy-style wiki.
Keep the question and model budgets fixed, and add more cross-wiki aliases,
stale facts, and NILs before drawing a saturation conclusion.

## Receipts

- [content-minimized receipt](../results/wiki-frontier-codex-loop-2026-08-02.json)
- [frontier loop](../../wiki_frontier_codex_loop.py)
- [receipt generator](../../wiki_frontier_receipt.py)
- [MCP harness boundary](wiki-frontier-harness-boundary-2026-08-02.md)
