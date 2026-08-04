# Outcome-aware release gate on memory and retrieval candidates

The architecture-neutral release gate was run against three sealed frontier
intervention receipts: generic generated memory, family-retrieved memory, and
self-feedback. Each source result had an independent fresh-environment replay
receipt with `all_passed=true`.

| candidate | verified replay | success lift over baseline | validity floor | exposure | decision |
| --- | --- | --- | --- | --- | --- |
| generated memory | pass | no (0/4 vs 0/4) | pass | 0 users / 0 tasks / 0% canary | quarantined |
| retrieved memory | pass | no (0/4 vs 0/4) | pass | 0 users / 0 tasks / 0% canary | quarantined |
| self-feedback | pass | no (0/4 vs 0/4) | fail (2 vs 0 invalid) | 0 users / 0 tasks / 0% canary | quarantined |

The gate completed collect, segment, cluster, retrieve, propose, replay, and
evaluate stages, then blocked release for every candidate. Monitoring was not
started and rollback was not needed because no candidate received exposure.
This is an empirical MLOps safety result: the same outcome predicate prevents
unverified or non-improving memory/feedback artifacts from silently entering a
user-facing loop. It is not evidence that the mechanisms are generally useless
and it does not implement the production Frankengate release service.

Receipts:

- `experiments/results/alfworld-luna-generated-memory-release-gate-2026-07-31.json`
- `experiments/results/alfworld-luna-retrieved-memory-release-gate-2026-07-31.json`
- `experiments/results/alfworld-luna-self-feedback-release-gate-2026-07-31.json`
