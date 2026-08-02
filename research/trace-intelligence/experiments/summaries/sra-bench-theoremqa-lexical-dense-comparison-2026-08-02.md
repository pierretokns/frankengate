# SRA-Bench TheoremQA dense retrieval control — 2026-08-02

## Result

On the pinned SRA-Bench corpus (26,262 skills) and all 747 TheoremQA
instances, `BAAI/bge-base-en-v1.5` beat both lexical controls:

| retriever | R@1 | R@5 | R@10 | R@50 | nDCG@10 |
|---|---:|---:|---:|---:|---:|
| BGE | `.6680` | `.8126` | `.8608` | `.9384` | `.7595` |
| BM25 | `.5716` | `.7631` | `.8072` | `.8956` | `.6922` |
| TF-IDF | `.4137` | `.6225` | `.6881` | `.8554` | `.5437` |

BGE's absolute lift over BM25 was `+.0964` at R@1 and `+.0535` at R@10.
This independently confirms the earlier ToolQA result that dense capability
retrieval can materially improve candidate recall on a large skill corpus.

## Interpretation

This is a retrieval result, not a skill-learning result. The benchmark measures
whether a skill associated with an instance is surfaced; it does not measure
whether the model incorporates the skill, executes its tools, solves the task,
or improves a later task. The SRA ToolQA execution probe was not counted here:
the first attempt used the wrong direct engine, and the corrected ReAct attempt
lacked the benchmark's external agenda corpus. Those are protocol/data failures,
not negative skill evidence.

The current architecture implication is therefore stronger but still staged:

```text
structured identifiers/scope -> lexical + dense candidate recall
-> compatibility and incorporation test -> execution/replay
-> changed-system and outcome gates -> release or refusal
```

Dense retrieval is justified as a candidate-generation lane across at least two
public task families. It must not authorize artifact reuse, ontology writes, or
skill promotion without compatibility, authority, independent execution, and
changed-system replay.

## Receipts

- [content-minimized receipt](../results/sra-bench-theoremqa-lexical-dense-comparison-2026-08-02.json)
- [independent verification](../results/sra-bench-theoremqa-lexical-dense-comparison-verification-2026-08-02.json)
- [ToolQA comparison](sra-bench-toolqa-lexical-dense-comparison-2026-08-02.md)

Raw retrieval outputs remain external and are referenced by SHA-256 only.
