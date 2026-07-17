# FrankenGate launch SLO contract

This is the operational contract for the internal Kubernetes launch. It turns
the reliability and performance beads into measurable gates. Percentiles are
computed over successful requests unless the row explicitly includes errors;
monthly error budgets are consumed by both user-visible failures and a gate
breach.

| Signal | Objective | Error budget / freeze trigger | Evidence |
| --- | --- | --- | --- |
| Gateway availability | 99.95% of non-maintenance HTTP requests return a provider response or an intentional policy response | Freeze if the rolling 30-day budget is exhausted | gateway request counters, excluding health probes |
| Successful stream start | 99.9% of accepted streams emit the first valid event within 5s | Freeze after two consecutive 15-minute windows below target | stream start and first-event counters |
| Gateway overhead | Added p95 latency <=10ms and added p50 <=5ms versus the identical direct path | Reject beta/release on either regression; benchmark exits 42 | `scripts/benchmark-gateway-overhead.sh` |
| Revocation | 99.9% of pods reject a revoked VK within 5s; hard upper bound 10s | Freeze and page on any measured stale acceptance over 10s | durable outbox cursor, invalidation age, stale-deny counter |
| Rotation | 99.9% of pods accept the new secret and reject the old secret within 5s | Freeze on stale acceptance or split-brain rotation | VK rotation/reload audit and pod convergence oracle |
| Overload | 100% of requests beyond admission capacity fail with an explicit bounded error; no unbounded queue growth | Freeze on process OOM, queue runaway, or silent drops | admission rejects, queue depth, process RSS |
| Recovery | A killed gateway pod becomes ready within 60s after its dependencies are healthy | Freeze if readiness bypasses the boot fence or exceeds 5m | readiness transitions and authority epoch |
| Control-plane data loss | RPO 0 for committed VK, authority, and reservation rows; RTO <=5m for a regional control-plane restart | Freeze on acknowledged-write loss or unrecoverable replay | PostgreSQL WAL/replay and outbox cursor evidence |

## Measurement rules

- Report request count, error count, denominator, p50, p95, and the time
  window with every SLO result. Never infer actual provider region or quota
  attribution from a model name alone.
- Separate direct-provider latency from gateway overhead. Do not mix cold-start,
  model variance, or failed requests into the successful latency percentile.
- A release freeze is a policy decision, not an automatic rollback. The release
  owner must record the breached signal, affected window, mitigation, and
  explicit approval before resuming publication.

## Ownership

- Gateway availability, stream start, overhead, overload, and recovery: gateway
  on-call.
- VK revocation/rotation and reservation durability: governance owner.
- RPO/RTO and PostgreSQL evidence: data-platform owner.

This contract does not claim that every objective is currently met; the related
beads remain open until production-like evidence exists.
