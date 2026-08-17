# Test matrix

Choose a track based on the failure mode. Keep the request mix constant while
changing one primary variable at a time.

| Track | Vary | Observe | Typical finding |
| --- | --- | --- | --- |
| Baseline | direct path vs gateway | added p50/p95/p99, CPU, allocations | gateway overhead or serialization cost |
| Load/capacity | constant RPS or concurrency | throughput, latency, queue age, RSS, GC | sustainable knee and first saturation |
| Stress/overload | drive beyond admission capacity | bounded errors, queue ceiling, recovery | runaway queues, OOM, unfair admission |
| Spike/ramp | abrupt and gradual arrival | HPA lag, pending pods, DB connections | scale-up delay or connection storm |
| Soak | representative load for hours | RSS/goroutines, pools, WAL, vacuum, drift | leaks, stale leases, retention growth |
| Agent/MCP | active agents, tool calls, result sizes, turns | tool slots, waiters, prompt bytes, provider calls | fan-out amplification or cancellation leaks |
| PostgreSQL | clients, pool sizes, locks, failover, WAL | active/max connections, p95 query time, waits | pool budget, lock inversion, vacuum pressure |
| Rollout/chaos | pod delete, node drain, provider/DB failure | admitted-work failures, stream reconnects, recovery | drain race, stale readiness, replay loss |

## Workload dimensions

Include all of the following when they are in scope:

- unary and streaming requests, including quiet streams and client aborts;
- successful, retrying, fallback, rate-limited, and provider-error requests;
- direct inference, MCP tool calls, multi-turn agents, code mode, and
  non-cooperative tool callbacks;
- small, representative, and maximum accepted request/result payloads;
- multiple tenants/virtual keys, governance accounting, cache hit/miss, and
  config reloads;
- pod counts at 1/3/10/production maximum, rollout surge, and scale-in;
- PostgreSQL writer failover, connection exhaustion, slow queries, lock waits,
  WAL growth, autovacuum/vacuum, and notification reconnects.

## Agent-specific protocol

Measure top-level request lifetime separately from individual LLM attempts.
Verify that tool concurrency is bounded per request and per pod, canceled
waiters do not execute, non-cooperative callbacks cannot block the request
forever, and every completed or canceled call releases slots. Include result
and conversation byte limits and assert that an oversized result fails closed.

## Run discipline

Use a warm-up, a measured window, and a cooldown. Repeat each point at least
three times or report variability. Pin image digest, source commit, config
hash, provider behavior, database version/instance class, node shape, and
metrics query revision. Keep raw output even when the run fails.
