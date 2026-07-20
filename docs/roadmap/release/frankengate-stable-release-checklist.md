# FrankenGate stable-release checklist

Status: preparation; no stable release claim.

## Passing local gates

- `make release-local-verify`
  - fork-owned branding checks;
  - Helm rendering and fork schema URL;
  - Rust analytics contract tests;
  - pricing mirror contract tests.
- `cargo test --manifest-path analytics-rs/Cargo.toml` currently passes 22
  tests covering protocol versioning, leasing, renewal, expiry/requeue,
  cancellation, completion, lineage, checkpoints, drain, retry, and durable
  SQLx lifecycle (when Postgres is configured).
- `cargo build --release --locked` plus the exact binary `--check` passes;
  Helm lint and enabled analytics-control-plane rendering pass. Analytics pods
  use a configurable startup probe for migration/database boot fencing.
- The analytics control-plane exposes bounded, tenant-scoped metadata
  projections for experiments, runs, evaluations, artifacts, and attempts;
  each projection sets the database tenant fence in-transaction and returns
  `503` when its durable query cannot be served.
- The fork-owned local overhead benchmark passes under elevated loopback
  networking with sub-0.1ms measured added p50/p95 overhead and zero errors;
  fixture bind failures now fail fast with an actionable diagnostic.
- Latest refresh at commit `79095b35c` measured `0.006ms` added p50 and
  `0.005ms` added p95 overhead with zero errors and no regression.
- Analytics Helm supports validated OCI digest pinning for the independently
  released control-plane image; chart lint and digest-qualified rendering
  pass.
- Pricing synchronization validates malformed documents and publishes an
  attributed FrankenGate envelope plus an immutable upstream snapshot.

## Required before a stable tag

- Choose the first stable semantic version and record compatibility/migration
  policy for the clean FrankenGate namespace.
- Run the full Go/UI release test matrix from a clean checkout, not only the
  local contract gate.
- Build and verify Linux/macOS binaries, Helm package, and Docker/OCI image
  digests from the same immutable commit.
- Generate the Helm repository index with the fork-owned
  `pierretokns/frankengate` release URL; reject any index that points back to
  `maximhq/bifrost`.
- Publish a real changelog with commit range and compatibility notes.
- Replace remaining fork-facing upstream URLs in UI/runtime surfaces and
  regenerate any derived assets.
- Verify GitHub release assets and GitHub Pages pricing snapshot externally.
- **External verification currently blocked:** three consecutive `gh release
  list --repo pierretokns/frankengate` attempts returned `error connecting to
  api.github.com`, while `git ls-remote` continued to resolve the fork remote
  and branch heads. Retry this gate when GitHub API connectivity recovers; do
  not infer release absence from the failed API calls.
- Do not claim the Rust analytics plane is production-ready until the durable
  PostgreSQL adapter, RLS integration tests, supervised worker runtime, and
  independent Kubernetes deployment/scaling evidence exist.

The checklist intentionally separates “local gates pass” from “stable release
published”; satisfying the former is necessary but not sufficient.
