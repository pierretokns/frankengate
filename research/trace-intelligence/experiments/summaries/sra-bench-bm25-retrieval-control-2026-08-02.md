# SRA-Bench BM25 retrieval control

Date: 2026-08-02  
Status: completed retrieval-only control; no skill-utility or enterprise claim

## Protocol

We fetched the public MIT-licensed [SR-Agents/SRA-Bench repository](https://github.com/oneal2000/SR-Agents), unpacked its 26,262-skill corpus, and ran the repository's own BM25 retriever at top-50 on all six released datasets. The run used `uv` in an isolated temporary environment. Raw skill content and rankings remain outside the research branch; only content-minimized metrics and hashes are committed.

The corpus contains 636 manually constructed gold skills mixed with 25,626 web-collected distractor skills. This is a capability-retrieval control, not a corporate trace corpus.

## Results

| dataset | queries | Recall@1 | Recall@5 | Recall@10 | Recall@50 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ToolQA | 1,430 | `.069930` | `.349650` | `.551049` | `.785315` | `.270200` |
| BigCodeBench | 1,140 | `.235804` | `.501813` | `.611462` | `.833816` | `.554247` |
| TheoremQA | 747 | `.571620` | `.763052` | `.807229` | `.895582` | `.692214` |
| LogicBench | 760 | `.119737` | `.273684` | `.360526` | `.580263` | `.225752` |
| MedCalc-Bench | 1,100 | `.292727` | `.487273` | `.691818` | `.924545` | `.446713` |
| CHAMP | 223 | `.132287` | `.307922` | `.360987` | `.543049` | `.272042` |

## Findings

1. **Capability retrieval is not uniform.** ToolQA and LogicBench have low
   rank-one recall despite reasonable top-50 coverage. A skill library can
   contain the right capability while failing to select it early.
2. **Top-k retrieval is only stage one.** The benchmark's own decomposition
   separates retrieval, incorporation, and end-task execution. A Recall@50
   result cannot show that the agent used the skill correctly.
3. **Distractor-heavy evaluation is essential.** The web-skill distractors
   provide a useful negative pool, but they are not enterprise same-surface,
   wrong-system, stale-authority, or cross-tenant negatives.
4. **The control is reproducible and useful.** It gives us a capability-RAG
   baseline before adding embeddings, reranking, progressive disclosure, or
   trace-derived skills. It does not validate any corporate artifact.

## Mapping to FrankenGate

Use the SRA pipeline as a public control with four explicit arms:

```text
BM25 / dense / hybrid / frontier retrieval
  -> no-skill / full-injection / progressive-disclosure incorporation
  -> independent task verifier
  -> Frankengate authority, changed-system, and release gates
```

For the corporate cohort, replace web distractors with reviewed negatives:
same surface/different system, temporal rename, stale authority, incompatible
schema, NIL/unclear, and result-preserving semantic collisions. Record pool
recall separately from incorporation precision and terminal task success.

## Claim boundary

This run establishes only a public BM25 retrieval control. It does **not**
establish skill quality, end-task utility, corporate alias quality, artifact
correctness, authorization safety, or cross-user transfer. The result is not a
reason to promote BM25, embeddings, or any retrieved skill into FrankenGate.

## Receipt

- Content-minimized receipt: [`sra-bench-bm25-retrieval-control-2026-08-02.json`](../results/sra-bench-bm25-retrieval-control-2026-08-02.json)
- Receipt generator: [`sra_bench_bm25_receipt.py`](../../sra_bench_bm25_receipt.py)
- Source repository: [oneal2000/SR-Agents](https://github.com/oneal2000/SR-Agents)
