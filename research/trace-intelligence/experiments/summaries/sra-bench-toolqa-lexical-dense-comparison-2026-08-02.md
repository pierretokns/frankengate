# SRA-Bench ToolQA lexical versus dense retrieval

Date: 2026-08-02  
Status: completed full ToolQA retrieval comparison; no incorporation or skill-utility claim

## Protocol

We evaluated all 1,430 ToolQA instances against the same 26,262-skill corpus
using the public SR-Agents implementations for BM25, TF-IDF, and
`BAAI/bge-base-en-v1.5`. BGE used the repository's query prefix and normalized
cosine retrieval. All three arms used top-50 candidate lists. Raw skill text,
embeddings, and rankings remain outside the research branch.

## Results

| Arm | Recall@1 | Recall@5 | Recall@10 | Recall@50 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | `.069930` | `.349650` | `.551049` | `.785315` | `.270200` |
| TF-IDF | `.069930` | `.209790` | `.349650` | `.559441` | `.188735` |
| BGE-base | `.321678` | `.737762` | `.833566` | `.967133` | `.585938` |

## Findings

1. **Dense retrieval materially improves candidate recall on ToolQA.** BGE
   raises Recall@1 by `+.251748` over BM25 and Recall@50 by `+.181818`.
2. **This is a candidate-recall result, not a skill result.** BGE can surface
   the correct capability more often; it does not show that the agent selects,
   incorporates, or executes the skill correctly.
3. **This differs from our EnterpriseRAG document result.** Generic MiniLM
   underperformed lexical retrieval there, while BGE succeeds on this
   capability corpus. Model choice and corpus/task structure matter; “dense is
   good” or “dense is bad” are both overgeneralizations.
4. **The next bottleneck is incorporation and execution.** ToolQA's high
   Recall@50 still leaves a large rank-one gap. We need a no-skill, BM25,
   TF-IDF, BGE, and oracle/selected-skill incorporation comparison with an
   independent ToolQA verifier.

## FrankenGate implication

Keep dense retrieval as an optional high-recall candidate lane behind exact
identifiers, source scope, and compatibility filters. Do not let a vector
score authorize a SQL/tool artifact. Use a frontier or human reviewer only on
the filtered shortlist, then require independent execution and changed-system
replay before release.

## Claim boundary

This establishes dense retrieval quality on a public capability benchmark. It
does not establish corporate alias quality, custom embedding transfer,
authorization safety, artifact correctness, or user benefit.

## Receipts

- Comparison receipt: [`sra-bench-toolqa-lexical-dense-comparison-2026-08-02.json`](../results/sra-bench-toolqa-lexical-dense-comparison-2026-08-02.json)
- Receipt generator: [`sra_bench_toolqa_dense_receipt.py`](../../sra_bench_toolqa_dense_receipt.py)
- Source repository: [oneal2000/SR-Agents](https://github.com/oneal2000/SR-Agents)
