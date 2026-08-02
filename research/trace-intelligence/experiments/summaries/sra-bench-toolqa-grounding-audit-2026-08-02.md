# ToolQA observation-grounding audit

Date: 2026-08-02  
Status: completed and independently verified; diagnostic only

## Question

When a skill arm fails its final answer, did the tool transcript already expose
the normalized gold answer? This is a diagnostic for separating retrieval/tool
execution failures from answer selection, formatting, or terminal protocol
failures.

## Rule

For each task, parse only `Observation N:` sections and check whether the
benchmark-normalized gold answer appears as a substring. This is deliberately
conservative about what it claims: an observation substring is not a semantic
label, a proof that the model understood it, or an independent outcome.

## Results

| arm | terminal correct | gold appears in observations | gold appears but terminal answer is wrong |
| --- | ---: | ---: | ---: |
| no-skill | `4/14` | `7/14` | `3/14` |
| BGE top-1 | `7/14` | `10/14` | `3/14` |
| BGE top-5 full injection | `6/14` | `8/14` | `2/14` |
| BGE progressive disclosure | `7/14` | `9/14` | `2/14` |
| gold oracle | `7/14` | `10/14` | `3/14` |

## Interpretation

The oracle and top-1 arms both exposed the normalized answer in 10/14
transcripts, yet three of those tasks still ended incorrectly. Progressive
disclosure exposed the answer in 9/14 and still had two evidence-present
terminal failures. This is strong diagnostic evidence that the current ceiling
is not only candidate retrieval: selecting the right observation, producing the
right tool action, and emitting the final typed answer are separate failure
points.

The result is not a proof of semantic understanding because substring matching
can over-count incidental text. The next study should replace this silver
signal with typed tool-result checks and blinded adjudication, while retaining
the exact terminal metric.

## Frankengate implication

Trace records need explicit intermediate evidence and terminal-result fields,
not only a final answer. Skill experiments should report at least:

1. candidate/skill availability;
2. tool-call validity and execution result;
3. evidence exposure and grounding; and
4. typed terminal correctness.

Otherwise an apparent skill failure cannot be attributed to retrieval,
incorporation, tool execution, or answer serialization.

## Receipts

- Receipt: [`sra-bench-toolqa-grounding-audit-2026-08-02.json`](../results/sra-bench-toolqa-grounding-audit-2026-08-02.json)
- Verification: [`sra-bench-toolqa-grounding-audit-verification-2026-08-02.json`](../results/sra-bench-toolqa-grounding-audit-verification-2026-08-02.json)
- Runner: [`sra_bench_toolqa_grounding_audit.py`](../../sra_bench_toolqa_grounding_audit.py)
- Verifier: [`verify_sra_bench_toolqa_grounding_audit.py`](../../verify_sra_bench_toolqa_grounding_audit.py)
