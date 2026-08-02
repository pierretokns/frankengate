# Frontier SSL-style multi-tool trajectory probe (2026-08-02)

This is the follow-up to the isolated-tool normalization probe. It tests
whether a frontier model can recover grounded scenes, transitions, and typed
actions when the source actually contains a multi-tool trajectory.

## Protocol

- Source: pinned public TRAJECT-Bench `parallel/` and `sequential/` records.
- Sample: 19 eligible hard trajectories: 10 parallel and 9 sequential. One
  domain had no eligible sequential multi-tool record, so the cohort is not
  padded with synthetic data.
- Model: `gpt-5.6-luna` through the Codex harness.
- Output: exact source tool order, one logical action per tool, grounded scene
  groups, optional transitions, and evidence quotes.
- Raw prompts/responses remain in `/private/tmp/ssl-trace-normalizer-probe-20260802-r2`.

## Results

| Measure | Mixed cohort |
| --- | ---: |
| Valid calls | `19/19` |
| Exact trajectory-type preservation | `1.000` |
| Exact tool-name order | `1.000` |
| Exact logical action count/order/resources | `1.000` |
| Evidence substring grounding | `.937294` |
| Fully grounded records | `.684211` |
| Mean scenes per trajectory | `2.631579` |
| Mean transitions per trajectory | `.631579` |
| Mean actions per trajectory | `4.842105` |
| Mean latency | `21.212s` |

Parallel and sequential subsets behaved differently:

| Subset | Records | Mean scenes | Mean transitions | Fully grounded |
| --- | ---: | ---: | ---: | ---: |
| Parallel | 10 | `2.3` | `.2` | `.800` |
| Sequential | 9 | `3.0` | `1.111` | `.556` |

## Interpretation

This is the first result showing that the representation is not limited by the
schema alone. When the source contains multiple tools and ordered outputs,
Luna emits actual scene groups and transitions while preserving every tool
identifier and action order. Sequential traces produce more transitions, as
expected.

The cost is a meaningful grounding drop: only 13/19 records had every evidence
quote grounded by the mechanical substring check, and the sequential subset
was weaker than the parallel subset. This is not a human semantic-label
assessment, but it is enough to reject automatic publication. Structural
normalization should remain a review proposal with evidence-level validation;
identifier/order fidelity can be accepted deterministically, while scene,
effect, and transition claims require adjudication or replay.

Compared with the isolated-tool probe (zero scenes and one action per record),
the multi-tool source unlocked the structural signal the SSL paper relies on.
The next decisive test is not another prompt: it is a labeled trajectory cohort
with retries, failures, tool-result effects, authority boundaries, temporal
changes, and independent terminal outcomes.

## Claim boundary

This measures grounded normalization mechanics on a small public cohort. It
does not measure retrieval lift, semantic alias quality, risk classification,
skill improvement, artifact reuse, or enterprise user outcomes.

## Receipts

- [machine-readable result](../results/traject-bench-ssl-trace-normalizer-probe-2026-08-02-r2.json)
- [independent verification](../results/traject-bench-ssl-trace-normalizer-probe-verification-2026-08-02-r2.json)
- [runner](../../traject_bench_ssl_trace_normalizer_probe.py)
- [verifier](../../verify_traject_bench_ssl_trace_normalizer_probe.py)
- [isolated-tool normalization probe](traject-bench-ssl-normalizer-probe-2026-08-02.md)

The initial parallel-only pilot is retained as a protocol-correction receipt:
[result](../results/traject-bench-ssl-trace-normalizer-probe-2026-08-02.json)
and [verification](../results/traject-bench-ssl-trace-normalizer-probe-verification-2026-08-02.json).
It is not pooled with the corrected mixed cohort.
