# SRA-Bench BM25 versus TF-IDF retrieval comparison

Date: 2026-08-02  
Status: completed lexical comparison; no embedding or skill-utility claim

## Protocol

Using the same public [SRA-Bench/SR-Agents](https://github.com/oneal2000/SR-Agents)
corpus, queries, and top-50 cutoff, we ran the repository's BM25 and TF-IDF
retrievers over all six datasets. The two arms share the same 26,262-skill
corpus and query splits. Raw rankings and skill text remain outside the
research branch.

## Results

| Dataset | BM25 R@1 | TF-IDF R@1 | Δ R@1 | BM25 R@50 | TF-IDF R@50 | Δ R@50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ToolQA | `.069930` | `.069930` | `.000000` | `.785315` | `.559441` | `-.225874` |
| BigCodeBench | `.235804` | `.208772` | `-.027032` | `.833816` | `.866023` | `+.032208` |
| TheoremQA | `.571620` | `.413655` | `-.157965` | `.895582` | `.855422` | `-.040161` |
| LogicBench | `.119737` | `.018421` | `-.101316` | `.580263` | `.377632` | `-.202631` |
| MedCalc-Bench | `.292727` | `.374545` | `+.081818` | `.924545` | `.983636` | `+.059091` |
| CHAMP | `.132287` | `.072123` | `-.060164` | `.543049` | `.514574` | `-.028475` |

## Interpretation

1. **There is no universal lexical winner.** BM25 is stronger on TheoremQA,
   LogicBench, CHAMP, and ToolQA at useful cutoffs; TF-IDF is stronger on
   MedCalc-Bench and has a small BigCodeBench top-50 recall advantage.
2. **The corpus/task interaction matters more than the label “retrieval.”** A
   single default ranker would hide large category-specific regressions.
3. **This supports a hybrid candidate layer, not automatic skill reuse.** The
   methods can be fused or routed by task family, but incorporation and
   end-task execution still need independent verifiers.
4. **It is not an embedding result.** Both methods are lexical controls. The
   next capability-retrieval arm is BGE/Contriever, followed by the same
   incorporation and execution protocol.

## FrankenGate implication

For the corporate trace cohort, retain multiple cheap retrieval views:
structured identifiers and scope, BM25, TF-IDF/field-weighted lexical, and
optional dense candidates. Measure candidate recall and hard-negative exposure
before any frontier selection. A model or skill is not promoted because one
retriever ranks it highly.

## Claim boundary

This receipt establishes only a reproducible public lexical comparison. It does
not establish corporate alias quality, embedding quality, skill quality,
artifact correctness, authorization safety, or user benefit.

## Receipts

- Comparison receipt: [`sra-bench-bm25-tfidf-comparison-2026-08-02.json`](../results/sra-bench-bm25-tfidf-comparison-2026-08-02.json)
- BM25 control: [`sra-bench-bm25-retrieval-control-2026-08-02.md`](sra-bench-bm25-retrieval-control-2026-08-02.md)
- Receipt generator: [`sra_bench_retrieval_comparison_receipt.py`](../../sra_bench_retrieval_comparison_receipt.py)
