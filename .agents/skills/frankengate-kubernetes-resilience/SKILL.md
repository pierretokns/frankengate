---
name: frankengate-kubernetes-resilience
description: Validate FrankenGate EKS rollouts, HPA behavior, scale-in, pod/node failure, ALB draining, and three-nines availability without losing streams or agent work. Use when testing zero/minimal-downtime upgrades, Karpenter/node drains, PDBs, readiness, or production game days.
---

# FrankenGate Kubernetes resilience

## Offline gate first

Run chart rendering, Terraform validation, capacity arithmetic, and the EKS
offline contracts before touching a cluster:

```bash
tests/kubernetes/eks/offline-contracts.sh
tests/kubernetes/eks/run-production-preflight.sh
```

The preflight must prove PostgreSQL authority, immutable image identity,
verify-only serving migrations, zero-unavailable/one-surge rollout, topology
spread, probes, PDB, HPA metrics, and connection headroom.

## Live drill

With an approved disruption window, run constant traffic containing unary,
long SSE/streaming, and active MCP-agent/tool requests. Test one pod delete,
one node cordon/drain, HPA scale-out and scale-in, ALB target deregistration,
and an Aurora writer promotion. Keep `maxUnavailable=0`, preserve the PDB, and
honor the deployed termination grace period.

## Pass criteria

- readiness withdraws before new work is admitted;
- active work completes or reconnects within the documented bounded drain;
- no acknowledged request silently disappears;
- replacement pods become ready within 60 seconds after healthy dependencies;
- no outage/error-budget breach beyond the SLO contract (99.9% is about 43m
  50s per 30-day month);
- HPA custom metrics remain fresh and missing metrics cannot cause unsafe
  scale-in;
- migration failure blocks the new revision without taking the old revision
  down, and rollback is tested with the same database compatibility epoch.

Record pod events, endpoint slices, ALB target health, request outcomes,
stream starts, agent tool outcomes, PostgreSQL failover state, and timestamps in
`tests/artifacts/perf/`. Local kind/k3d/Colima proves application contracts;
it does not prove AWS networking, node capacity, or Aurora behavior.
