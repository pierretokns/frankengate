# Deterministic terminal-fallback pilot (2026-07-31)

The original Llama SQL runs were terminal-protocol nulls: the model generated
no accepted terminal action even when it had a candidate query. To separate
query generation from terminal-call formatting, the harness was rerun with an
arm-independent controller:

> submit the most recent successful authorized candidate, or abstain when no
> successful candidate exists.

The controller never reads gold SQL, hidden outcomes, or semantic labels. It is
recorded in each aggregate as
`submit-most-recent-successful-authorized-attempt-or-abstain-v1`.

| cohort | arm | tasks | fallback used | successful SQL executions | semantic correct | semantic incorrect |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| held-out broker | no skill | 4 | 4 | 0 | 0 | 0 |
| held-out broker | formatting placebo | 4 | 4 | 0 | 0 | 0 |
| held-out broker | trace-mined discipline | 4 | 4 | 0 | 0 | 0 |
| car-dealership pilot | no skill | 4 | 4 | 0 | 0 | 0 |
| car-dealership pilot | formatting placebo | 4 | 4 | 0 | 0 | 0 |
| car-dealership pilot | trace-mined discipline | 4 | 4 | 1 | 0 | 1 |

The fallback makes the evaluator reachable, but it does not create a skill
benefit: there were zero semantic wins in both cohorts. The single trace-mined
car-dealership execution was wrong. The broker fold still produced no valid
candidate SQL, so it remains a protocol/generation null rather than a quality
estimate.

A second held-out broker slice containing four `questions_gen_postgres` tasks
also produced zero successful SQL in all three arms. It is retained as a
separate aggregate so task-category failures are not conflated with the first
advanced-query slice.

This is a harness-repair result, not a causal skill result. The next required
experiment is a larger family-disjoint replay with a model/runtime that can
produce authorized SQL, all proposal arms, and an independent semantic/security
verifier.

Machine-readable results: [`defog-broker-fallback-openai-llama-2026-07-31.json`](../results/defog-broker-fallback-openai-llama-2026-07-31.json), [`defog-broker-fallback-qgen-llama-2026-07-31.json`](../results/defog-broker-fallback-qgen-llama-2026-07-31.json), and [`defog-car-fallback-llama-2026-07-31.json`](../results/defog-car-fallback-llama-2026-07-31.json).
