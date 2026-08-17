---
name: frankengate-performance-testing
description: Design and run evidence-driven performance, capacity, soak, agent-saturation, PostgreSQL, rollout, and chaos tests for FrankenGate. Use when evaluating RPS, concurrency, latency, HPA behavior, MCP/agent load, EKS scale-in, Aurora/PostgreSQL pressure, 24/7 reliability, or production readiness.
---

# FrankenGate performance testing

Use this skill to turn a scale question into a reproducible workload, a bounded
test, and an evidence-backed decision. Keep PostgreSQL as the production
control-plane authority; do not introduce Redis/Kafka merely to make a test
convenient.

## Quick workflow

1. Write the workload envelope: request mix, payload sizes, provider latency,
   stream duration, active agents/tools, tenants, target replicas, and database
   limits. Separate admitted work from rejected work.
2. Define SLOs before running: success/error budget, p50/p95/p99 latency,
   queue age, active work, RSS, goroutines, PostgreSQL connections/WAL/locks,
   and recovery time. Include a three-nines outage budget when relevant.
3. Run an identical direct-vs-gateway baseline before optimizing overhead.
4. Test in this order: baseline, load/capacity, overload, spike/ramp, soak,
   agent/MCP saturation, database pressure, then failure/rollout drills.
5. Repeat at 1, 3, 10, and the proposed production replica counts. Record the
   first limit and its slope; never infer a 400-user or hundreds-of-agents
   capacity number from a single small run.
6. Save commands, immutable image/config identity, workload, raw output,
   dashboards, and environment in a dated artifact. Label local Kubernetes,
   real EKS, and Aurora evidence separately.

## Repository entry points

- Gateway overhead: `scripts/benchmark-gateway-overhead-local.sh` and
  `scripts/benchmark-gateway-overhead.sh`.
- Local PostgreSQL/Kubernetes authority and active-work tests:
  `tests/kubernetes/local-aurora/run-vk-coherence.sh`.
- EKS contract checks: `tests/kubernetes/eks/offline-contracts.sh` and
  `tests/kubernetes/eks/run-production-preflight.sh`.
- Controlled EKS pod replacement/node-drain/Aurora drill:
  `tests/kubernetes/eks/run-resilience-drill.sh`.
- SLO and claim boundaries: `docs/roadmap/reliability/frankengate-slo-contract.md`.

## Non-negotiable conclusions

- Mock providers measure gateway mechanics, not provider quota, network, or
  model latency capacity.
- Local kind/k3d/Colima tests validate behavior and contracts, not EKS
  scheduling, ALB deregistration, cross-AZ latency, or Aurora failover.
- A green readiness probe does not prove budget enforcement, event convergence,
  or upgrade safety; test each explicitly.
- Treat missing metrics, partial custom-metric results, and stale authority as
  failures or unknowns—not as zero load.
- Optimize only after the bottleneck is measured and add a regression test or
  operational guard for every accepted fix.

For test shapes, metrics, and pass/fail evidence, read [test-matrix.md](references/test-matrix.md) and [evidence-and-gates.md](references/evidence-and-gates.md).
