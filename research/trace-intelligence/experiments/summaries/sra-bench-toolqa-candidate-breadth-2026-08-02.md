# ToolQA candidate breadth and skill incorporation

Date: 2026-08-02  
Status: completed and independently verified; public benchmark only

## Question

When retrieval returns several plausible skills, does broader context or
progressive disclosure let a frontier model recover tasks missed by top-1
retrieval? This separates three failure modes:

1. the correct skill is absent from retrieval;
2. the correct skill is present but the model does not select it; and
3. the model selects a skill but cannot execute it or emit the strict answer.

## Protocol

We used one fixed ToolQA instance from each of the 14 skill families. Every arm
used the same `gpt-5.6-luna` Codex-subscription proxy, ToolQA databases, zero
temperature, 15-step cap, and strict unchanged ToolQA evaluation:

| arm | skill presentation |
| --- | --- |
| no-skill | no retrieved skill |
| BGE top-1 | one dense-retrieved skill |
| BGE top-5 full injection | all five dense candidates shown and loaded |
| BGE progressive disclosure | five candidates shown; model chooses `LoadSkill[index]` |
| gold oracle | exact annotated skill |

Raw transcripts remain external and are represented by SHA-256 hashes in the
receipt. The ToolQA archive is also hashed rather than committed.

## Results

| arm | strict correct | accuracy | exact gold skill loaded | mean skills loaded |
| --- | ---: | ---: | ---: | ---: |
| no-skill | 4/14 | `.2857` | 0/14 | `0.00` |
| BGE top-1 | 7/14 | `.5000` | 6/14 | `1.00` |
| BGE top-5 full injection | 6/14 | `.4286` | 10/14 | `5.00` |
| BGE progressive disclosure | 7/14 | `.5000` | 10/14 | `.71` |
| gold oracle | 7/14 | `.5000` | 14/14 | `1.00` |

The dense candidate set contained the gold skill in 10/14 tasks at top-5,
versus 6/14 at top-1. However, top-5 full injection lost one task relative to
top-1, while progressive selection recovered the top-1 score but did not beat
it. Both BGE top-1 and progressive arms tied the gold oracle.

## Interpretation

- **Broader retrieval improves availability, not outcome.** The candidate
  recall gain (`6/14 -> 10/14`) did not translate into terminal accuracy.
- **Unfiltered breadth creates distractors.** Full top-5 injection was worse
  than top-1, so “retrieve more and stuff it into context” is not a safe skill
  architecture.
- **Selection helps control context, but not enough here.** Progressive
  disclosure avoided the top-5 penalty and loaded only `.71` skills per task,
  yet remained tied with top-1 and the oracle.
- **The remaining ceiling is incorporation/execution/output, not retrieval
  alone.** The oracle did not exceed 7/14. Some failures are strict answer
  formatting or malformed tool calls, so this experiment does not isolate model
  reasoning from protocol compliance.

This is evidence for a staged skill system: retrieve a small candidate set,
select or load one candidate, validate tool-call syntax, and independently
check the terminal result. It is not evidence that a skill should be promoted,
that embeddings improve enterprise work, or that cross-user transfer exists.

## Frankengate implication

The next useful experiment is not a larger context window. It is a factorial
execution study with (a) strict versus normalized answer scoring, (b) tool-call
repair/structured action validation, (c) held-out skill families, and (d) a
changed-environment replay gate. Only that can tell us whether skill retrieval
improves actual tool outcomes rather than benchmark formatting.

## Receipts

- Receipt: [`sra-bench-toolqa-candidate-breadth-2026-08-02.json`](../results/sra-bench-toolqa-candidate-breadth-2026-08-02.json)
- Verification: [`sra-bench-toolqa-candidate-breadth-verification-2026-08-02.json`](../results/sra-bench-toolqa-candidate-breadth-verification-2026-08-02.json)
- Runner: [`sra_bench_toolqa_candidate_breadth_receipt.py`](../../sra_bench_toolqa_candidate_breadth_receipt.py)
- Verifier: [`verify_sra_bench_toolqa_candidate_breadth_receipt.py`](../../verify_sra_bench_toolqa_candidate_breadth_receipt.py)
