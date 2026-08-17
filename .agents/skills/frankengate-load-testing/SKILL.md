---
name: frankengate-load-testing
description: Run reproducible FrankenGate throughput, latency, overload, and soak tests with direct-path baselines and production-safe evidence. Use when measuring RPS, p95/p99 latency, gateway overhead, capacity, queue growth, memory growth, or 24/7 endurance.
---

# FrankenGate load testing

## Quick start

1. State the SLO and workload before choosing a rate. Include request type,
   payload size, stream ratio, provider latency, failure rate, and concurrency.
2. Run the same workload against the direct fixture/provider path and the
   gateway. Keep the provider deterministic when measuring gateway overhead.
3. Prefer constant-rate tests for capacity and ramp/soak tests for saturation:

```bash
N=200 scripts/benchmark-gateway-overhead-local.sh
./benchmark -provider bifrost -rate 500 -duration 60 -output result.json
./benchmark -provider bifrost -users 500 -duration 600 -ramp-up -ramp-up-duration 120 -output soak.json
```

## Required evidence

- Report denominator, successes, failures, p50, p95, p99, first-byte/stream
  start latency, queue depth, admission rejects, RSS, goroutines, CPU, and
  PostgreSQL connections for the full window.
- Separate successful-request latency from errors and separate provider time
  from gateway-added time. Never inherit upstream Bifrost benchmark claims.
- Test at 1, 3, 10, and the intended production replica count only when the
  environment can supply the corresponding node, database, and provider
  headroom. A local result is a harness or slope result, not EKS capacity.

## Pressure matrix

Run normal load, a burst above admission capacity, large bodies/results,
streaming, provider throttling/errors, and a 30-minute-plus soak. Assert that
queues remain bounded, overload returns an explicit bounded error, RSS does not
trend upward, and recovery returns metrics to baseline.

## Release rule

Use the SLO contract in `docs/roadmap/reliability/frankengate-slo-contract.md`.
Record every failure and environment limitation in `tests/artifacts/perf/`;
do not call a local mock-provider run a production readiness proof.
