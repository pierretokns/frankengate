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

The fixture expects the cluster to provide a default dynamic `ReadWriteOnce`
storage class. The PostgreSQL image is pinned by manifest-list digest; changing
the tag or digest requires an explicit fixture review and a fresh SQL smoke
test on every CI architecture.

Apply and wait:

```sh
kubectl apply -f tests/kubernetes/local-aurora/postgres.yaml
kubectl rollout status statefulset/postgres -n frankengate-test --timeout=120s
```

## Three-pod virtual-key coherence proof

`run-vk-coherence.sh` builds (or accepts) a Linux FrankenGate binary, starts
three isolated gateway pods against the shared PostgreSQL authority, and
proves the following sequence against each pod's in-memory governance cache:

1. create on pod A converges to all three pods;
2. rotate on pod B replaces the value on all three pods;
3. delete on pod C removes the key from all three pods;
4. PostgreSQL records exactly `reload`, `reload`, `delete` in monotonic order;
5. a replacement pod replays the complete history without resurrecting the
   deleted key or wedging on the historical reload events.

The convergence oracle runs inside the cluster once per second with an
eight-second hard deadline. `kubectl` startup latency is therefore excluded
from the measured propagation window.

Run against the current Kubernetes context:

```sh
tests/kubernetes/local-aurora/run-vk-coherence.sh
```

For an offline cluster, provide an already-built Linux binary and an image tag
present in the node's containerd cache:

```sh
FRANKENGATE_BINARY=/tmp/frankengate-vk \
POSTGRES_IMAGE='docker.io/pgvector/pgvector:0.8.1-pg16@sha256:33198da2828a14c30348d2ccb4750833d5ed9a44c88d840a0e523d7417120337' \
tests/kubernetes/local-aurora/run-vk-coherence.sh
```

Set `KEEP_FIXTURE=1` to retain the disposable pods for inspection. The runner
uses a temporary in-cluster HTTP service to transfer the binary because a
container-image build is not part of this coherence assertion. It discovers
that Service's ClusterIP and renders a temporary gateway manifest, so the
checked-in template contains no cluster-specific address.

To prove the shipped container rather than a loose binary, pass an immutable
image digest. This path uses the image's own entrypoint and command, requires
three distinct Kubernetes nodes, and runs the same create/rotate/delete/restart
oracle against the artifact:

```sh
FRANKENGATE_IMAGE='ghcr.io/pierretokns/frankengate@sha256:<manifest-digest>' \
tests/kubernetes/local-aurora/run-vk-coherence.sh
```

Release CI must use this mode. The loose-binary mode remains useful for fast
local iteration but is not evidence that a published image contains the fix.

This is a same-cluster, shared-authority coherence proof. Image mode proves
cross-node scheduling and the published container entrypoint; loose-binary mode
does not. Neither mode proves cross-region Aurora behavior, production image
hardening, HPA behavior, or real Aurora failover.

Delete the complete fixture, including its persistent volume claim:

```sh
kubectl delete namespace frankengate-test
```
