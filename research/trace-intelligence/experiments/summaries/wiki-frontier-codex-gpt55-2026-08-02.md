# Codex `gpt-5.5` wiki loop — 2026-08-02

The same 20-case structured-action loop used for the Luna run was repeated
with `gpt-5.5` through the Codex CLI subscription. The fixture has 1/5/10/25
synthetic wikis, five cases per size (exact identifier, semantic paraphrase,
alias, cross-wiki disambiguation, and NIL), a hybrid raw backend, and a
five-action limit.

| wikis | target answer | gold searched | gold loaded | NIL abstention | errors | p95 latency |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 33.6 s |
| 5 | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 38.1 s |
| 10 | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 36.8 s |
| 25 | 1.00 | 1.00 | 1.00 | 1.00 | 0 | 41.8 s |

On this easy synthetic contract, `gpt-5.5` did not show the 25-wiki
cross-wiki completion failure observed in the Luna run. This is a model
comparison, not evidence that one model is universally better: the sample is
only 20 cases, the questions are generated, and the backend is local.

The requested `gpt-5.6` model was also probed. The Codex CLI returned an
explicit API error that `gpt-5.6` is unsupported when using Codex with this
ChatGPT account, so no fabricated comparison is reported.

Native MCP remains unmeasured in both model runs. The earlier non-interactive
native-MCP probe cancelled before `tools/call`; the structured action loop is
an executable contract substitute, not native MCP evidence.

Receipt: [content-minimized result](../results/wiki-frontier-codex-gpt55-2026-08-02.json)
