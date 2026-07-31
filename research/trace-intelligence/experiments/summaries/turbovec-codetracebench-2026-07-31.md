# TurboVec CodeTraceBench dense-index checkpoint (2026-07-31)

TurboVec was independently built from the local source checkout
`/private/tmp/turbovec-research` (`turbovec` 0.9.0 Rust crate, Python binding
0.8.0) and evaluated on the same 145-document, 99-query CodeTraceBench dense
cohort used by the existing retrieval work. The Qwen3-Embedding-0.6B vectors
were regenerated from the pinned local model snapshot; vectors and trajectory
content remain outside Git.

## Results

| index | task Recall@20 | delta vs exact float | task Top-1 | filtered exact-top-k overlap | mean query ms | persisted bytes |
|---|---:|---:|---:|---:|---:|---:|
| exact float reference | 0.6667 | — | 0.6364 | — | — | — |
| TurboVec 2-bit | 0.6667 | 0.0000 | 0.6364 | 0.9483 | 0.1125 | 47,070 |
| TurboVec 4-bit | 0.6515 | -0.0152 | 0.6364 | 0.9834 | 0.1279 | 84,190 |

The filtered test used deterministic per-query allowlists averaging 67.7 of 145
documents. Every returned ID was inside its allowlist. The persisted-index
load/delete round trip passed for both bit widths. Upstream TurboVec unit and
integration tests also passed (including filtering, deletion, persistence,
concurrency, and correctness suites).

## Interpretation

TurboVec is a credible **local dense-index component** when memory footprint or
filtered vector latency is the measured bottleneck: it provides online ingest,
compact persistence, and in-kernel allowlists without a separate service. On
this small cohort, 2-bit quantization matched the exact dense Recall@20 and
4-bit lost 1.52 percentage points; the result is not a general quality claim.

It is not an authority, relational trace store, RLS policy engine, deletion
ledger, lexical/BM25 engine, or skill-learning system. The allowlist is an
application-provided candidate boundary, so Frankengate would still need
PostgreSQL to decide authorization and deletion before invoking TurboVec. No
backend promotion or architecture change is authorized by this checkpoint;
the next gate is a larger labeled workload with joint authorization/deletion
and downstream skill-mining utility.

Artifact: `../results/turbovec-codetracebench-2026-07-31.json`.
