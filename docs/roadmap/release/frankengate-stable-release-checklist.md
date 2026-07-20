# FrankenGate stable-release checklist

Status: preparation; no stable release claim.

## Passing local gates

- `make release-local-verify`
  - fork-owned branding checks;
  - Helm rendering and fork schema URL;
  - Rust analytics contract tests;
  - pricing mirror contract tests.
- Rust contract currently has six passing tests for protocol versioning,
  leasing, renewal, expiry/requeue, cancellation, completion, and lineage.
- Pricing synchronization validates malformed documents and publishes an
  attributed FrankenGate envelope plus an immutable upstream snapshot.

## Required before a stable tag

- Choose the first stable semantic version and record compatibility/migration
  policy for the clean FrankenGate namespace.
- Run the full Go/UI release test matrix from a clean checkout, not only the
  local contract gate.
- Build and verify Linux/macOS binaries, Helm package, and Docker/OCI image
  digests from the same immutable commit.
- Publish a real changelog with commit range and compatibility notes.
- Replace remaining fork-facing upstream URLs in UI/runtime surfaces and
  regenerate any derived assets.
- Verify GitHub release assets and GitHub Pages pricing snapshot externally.
- Do not claim the Rust analytics plane is production-ready until the durable
  PostgreSQL adapter, RLS integration tests, supervised worker runtime, and
  independent Kubernetes deployment/scaling evidence exist.

The checklist intentionally separates “local gates pass” from “stable release
published”; satisfying the former is necessary but not sufficient.
