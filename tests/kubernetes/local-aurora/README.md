# Local Aurora-compatible test substrate

This fixture supplies a PostgreSQL 16 database inside the disposable
`frankengate-test` Kubernetes namespace. It is intended for deterministic
multi-process and multi-pod tests of PostgreSQL semantics used by FrankenGate:

- transactions and compare-and-swap updates;
- durable outbox rows and monotonic cursors;
- `LISTEN`/`NOTIFY` as a wakeup hint rather than an event authority;
- advisory or row locks, idempotency, leases, and reconciliation;
- disconnect, restart, notification loss, and cold-bootstrap recovery.

It is not an Aurora emulator and does not prove Aurora writer failover, RDS
Proxy listener behavior, parameter-group limits, global database behavior,
cross-AZ latency, or AWS control-plane integration. Those require a separate
real-Aurora conformance run before a release claim.

The checked-in password is deliberately test-only. This manifest must never be
used for a shared or production environment.

Apply and wait:

```sh
kubectl apply -f tests/kubernetes/local-aurora/postgres.yaml
kubectl rollout status statefulset/postgres -n frankengate-test --timeout=120s
```

Delete the complete fixture, including its persistent volume claim:

```sh
kubectl delete namespace frankengate-test
```
