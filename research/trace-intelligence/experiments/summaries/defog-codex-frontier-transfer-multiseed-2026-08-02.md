# Frontier artifact-transfer multiseed screen (2026-08-02)

## Design

This is a matched four-task, three-seed family-transfer screen using the
frontier Codex loopback proxy. Every seed runs the same `no_skill`,
`formatting_placebo`, and `trace_mined_terminal_discipline` arms. The result
receipt is independently re-executed by the semantic verifier against the
pinned PostgreSQL benchmark. All 36 arm episodes were authority-valid,
submitted, and independently verified.

## Shared-cluster result

| arm | semantic correct | rate |
| --- | ---: | ---: |
| no skill | 6 / 12 | 0.500 |
| formatting placebo | 10 / 12 | 0.833 |
| trace-mined terminal discipline | 5 / 12 | 0.417 |

Paired comparisons (task × seed blocks):

* trace-mined vs placebo: risk difference −0.417; exact McNemar p=0.125
* trace-mined vs no-skill: risk difference −0.083; exact McNemar p=1.0
* placebo vs no-skill: risk difference +0.333; exact McNemar p=0.21875

There were zero unauthorized observations and every arm submitted a terminal
answer. The trace-mined artifact therefore does not earn promotion in this
screen; the placebo outperforming it is a direct warning that context/format
effects and stochastic variation dominate the observed contrast.

## Isolation follow-up

`frontier_transfer_docker_isolated.py` reruns the same protocol with one
disposable PostgreSQL 16 container, mapped port, governed application role,
Codex loopback proxy, raw-audit directory, and verifier-audit directory per
seed. It is intentionally a separate receipt family: results are not pooled
with the shared-cluster screen until both semantic and security verification
passes.

The two-seed isolated aggregate also passed independent verification:

| arm | semantic correct | rate | submitted |
| --- | ---: | ---: | ---: |
| no skill | 5 / 8 | 0.625 | 8 / 8 |
| formatting placebo | 3 / 8 | 0.375 | 7 / 8 |
| trace-mined terminal discipline | 4 / 8 | 0.500 | 6 / 8 |

Trace-mined vs no-skill was −0.125 (exact McNemar p=1.0); trace-mined vs
placebo was +0.125 (p=1.0). The direction changes relative to the shared
cluster, as expected from frontier stochasticity, but neither comparison is
statistically persuasive and the artifact does not meet the promotion rule.
The isolated run proves the database/process boundary, not a causal skill
gain.

## Claim boundary

This is evidence about this small held-out family and protocol only. It is not
evidence that trace mining is universally harmful, nor that a database or
embedding choice caused the outcome. A promotion-capable experiment still
needs a length/token-matched neutral control, source-literal redaction,
renamed/paraphrased task mutants, train-only artifact selection, a second
harness, independent verifiers, and task/family-clustered analysis.
