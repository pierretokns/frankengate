# ToolQA semantic adjudication and incorporation bounds

Date: 2026-08-02  
Status: completed; frontier diagnostic, not a human-label or promotion result

## Question

The strict ToolQA score mixes wrong answers, harmless representation changes,
and answers that a human may regard as equivalent. We ran two independent
frontier adjudication passes over every strict failure:

1. a normal rubric allowing unambiguous semantic/time/unit equivalence; and
2. a skeptical rubric that rejects extra intervals, omitted values, rounded
   values, and category-only answers.

The judge saw the question, gold answer, candidate answer, and transcript. It
could not execute tools, browse, or change the benchmark. Raw judgments remain
external and are represented by hashes in the receipt.

## Results

`Accepted lower bound` counts only strict successes plus cases both judges
accepted as `correct_semantic` or `format_only`. `Accepted upper bound` also
includes cases where the two passes disagreed.

| arm | strict | accepted lower bound | accepted upper bound | judge disagreements |
| --- | ---: | ---: | ---: | ---: |
| no-skill | `4/14` | `6/14` | `7/14` | `1` |
| BGE top-1 | `7/14` | `10/14` | `10/14` | `0` |
| BGE top-5 full injection | `6/14` | `7/14` | `7/14` | `0` |
| BGE progressive disclosure | `7/14` | `9/14` | `10/14` | `1` |
| gold oracle | `7/14` | `8/14` | `8/14` | `0` |

Across the 39 strict failures, 28 were incorrect by both passes, 9 were
accepted by both, and 2 were judge disagreements. The two disagreements are
why the receipt reports an interval rather than a single semantic score.

## Interpretation

- BGE top-1 remains a positive candidate arm under either strict or adjudicated
  scoring (`7/14` strict, `10/14` accepted lower bound).
- Top-5 full injection remains inferior (`6/14` strict, `7/14` accepted), so
  the distractor penalty is not explained only by answer formatting.
- Progressive disclosure is between `9/14` and `10/14`, but its interval still
  overlaps top-1 and does not beat the gold oracle with confidence.
- The gold oracle is only `8/14` after the conservative dual-pass audit. Better
  retrieval cannot fix the remaining execution, reasoning, or protocol errors.

These are frontier-model evaluator bounds, not ground truth. The next required
study is typed tool-result validation plus blinded human/SME adjudication on a
larger family-disjoint cohort. No skill or embedding is promoted from this
result.

## Frankengate implication

Skill experiments should report three distinct quantities:

1. strict benchmark terminal correctness;
2. typed/semantic terminal correctness with an auditable rubric; and
3. adjudication disagreement/abstention.

Collapsing them into one score hides whether a proposal improved retrieval,
incorporation, tool execution, or answer serialization.

## Receipts

- Receipt: [`sra-bench-toolqa-semantic-adjudication-2026-08-02.json`](../results/sra-bench-toolqa-semantic-adjudication-2026-08-02.json)
- Verification: [`sra-bench-toolqa-semantic-adjudication-verification-2026-08-02.json`](../results/sra-bench-toolqa-semantic-adjudication-verification-2026-08-02.json)
- Runner: [`sra_bench_toolqa_semantic_adjudication.py`](../../sra_bench_toolqa_semantic_adjudication.py)
- Receipt builder: [`sra_bench_toolqa_semantic_adjudication_receipt.py`](../../sra_bench_toolqa_semantic_adjudication_receipt.py)
- Verifier: [`verify_sra_bench_toolqa_semantic_adjudication_receipt.py`](../../verify_sra_bench_toolqa_semantic_adjudication_receipt.py)
