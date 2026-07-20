# FrankenGate analytics control plane

This is the first isolated Rust vertical slice for the analytics plane. It is
deliberately dependency-free: the `JobStore` proves the lifecycle invariants
before an HTTP server, PostgreSQL persistence, or worker runtime is selected.

## Adoption gates

Potential FrankenSuite/Dicklesworthstone/Doodlestein components are not runtime
dependencies yet. Each candidate must provide:

1. a pinned upstream release and compatible license/NOTICE entry;
2. a measured improvement over the current slice (latency, recovery, memory,
   or owned lifecycle code);
3. deterministic duplicate-delivery, cancellation, shutdown, and worker-death
   tests; and
4. an explicit stop decision if the candidate does not close a named gap.

The production direction remains a separately deployed Rust control plane with
PostgreSQL as the authoritative contract store. It must never execute analytics
jobs inside gateway inference workers.

The current in-memory contract already covers:

- monotonic delivery attempts across lease expiry and explicit retry;
- optional hard queue capacity with typed admission rejection;
- atomic tenant-scoped claiming, bounded listings, and queue statistics;
- owner-only heartbeats, checkpoints, completion, and failure transitions;
- graceful worker draining and duplicate-delivery idempotency; and
- tenant-scoped cancellation/retry plus reproducible experiment lineage; and
- terminal, same-tenant replay jobs with explicit `replay_of` lineage.

These are protocol and test guarantees, not a claim of durable persistence or
production API availability. The PostgreSQL service, supervision runtime, and
independent Helm deployments remain separate implementation gates.

`migrations/001_analytics_contract.sql` is the first durable schema contract.
It enables tenant RLS and stores only artifact manifests in PostgreSQL; artifact
bytes remain in the configured object store.

Run the current contract tests with:

```bash
cargo test --manifest-path analytics-rs/Cargo.toml
```

The dependency-free operator smoke check exercises submit → lease → complete
and verifies the typed terminal outcome:

```bash
cargo run --manifest-path analytics-rs/Cargo.toml -- --check
```
