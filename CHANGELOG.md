# Changelog

All notable FrankenGate changes are recorded here from the fork's git history.
Version entries describe compatibility risk explicitly; release automation must
attach the matching immutable tag and artifact digests.

## Unreleased

### Beta `v0.3.20-beta.4`

- Added the isolated Rust analytics control plane for tenant-scoped
  experiments, runs, evaluations, artifact manifests, replay lineage, and
  governed worker leases. PostgreSQL is the authoritative store; inference
  remains on the Go gateway boundary.
- Added durable terminal run outcomes with idempotent conflict handling and
  tenant/actor authorization checks.
- Added independent analytics-control-plane Helm deployment, autoscaling,
  readiness, and database-connection budget configuration.
- Bedrock Mantle GPT-Soul, GPT-Luna, GPT-Terra, and GPT-Sol aliases now use
  the `/openai/v1/responses` route and scalar plain-message input required by
  the Mantle GPT-5.6 contract; structured tool input remains array-shaped.
- Release verification covers Go provider regression tests, Rust contract
  tests/build, Helm rendering, branding checks, and the pricing mirror.

### Compatibility

- This remains a prerelease (`0.3.20-beta.4`). Existing Bifrost-compatible
  chart/value identifiers are retained; the Rust analytics API is additive
  and opt-in. Stable promotion still requires successful external workflow
  and artifact verification.

### Beta `v0.3.17-beta.1`

- Bedrock Mantle GPT-5.6 Responses requests with plain message input now use
  the scalar `input` form required by Mantle; structured tool-call input stays
  in array form. Published in the beta binary release with checksums.

### Fixed

- Helm chart defaults and documentation now agree on the `v0.3.19` gateway
  image tag, avoiding fresh installs silently selecting an older binary.
- Helm now rejects durable analytics deployments that enable a `ServiceMonitor`
  without an explicit tenant scope, preventing local-only queue metrics from
  being mistaken for Postgres-backed production metrics.
- The local overhead benchmark now fails fast with an actionable loopback/port
  diagnostic when its fixture cannot bind, instead of emitting misleading
  request errors and an eventual empty-sample failure.
- Replay admission now preserves a typed capacity-exceeded outcome instead of
  collapsing bounded-queue rejection into a generic lease error.
- Config schema validation accepts the fork-owned `FRANKENGATE_SCHEMA_URL`
  override while retaining `BIFROST_SCHEMA_URL` compatibility.
- OCI development images now identify themselves as `vdev-build` instead of
  the ambiguous `vunknown`; release builds continue to inject their semver.
- The OCI entrypoint now forwards `--version`/`-version`, allowing a detached
  image smoke test to verify the embedded FrankenGate version without starting
  the gateway.
- `/readyz` now fails closed until the VK invalidation and principal-authority
  consumers have completed bootstrap and remain fresh; `/livez` remains process-only.
- Release vulnerability checks compile `govulncheck` once per job instead of
  recompiling it for every Go module.

### Added

- Analytics control-plane Helm deployments now use a configurable startup
  probe window for migration/database boot fencing, preventing slow Aurora
  startup from triggering premature liveness restarts.
- Helm pricing defaults now consume the fork's cached GitHub Pages snapshot;
  the scheduled mirror retains the upstream source only as an explicit input.

- Added a separately deployable SQLx/Postgres analytics control plane with
  tenant-scoped experiments, reproducible runs, evaluations, artifact lineage,
  replay, and terminal outcomes.
- Added durable worker APIs for lease claim, renewal, checkpoint, completion,
  failure, cancellation, retry, replay, drain, and expired-lease recovery;
  ownership is enforced by PostgreSQL row-level security and `SKIP LOCKED`.
- Added an opt-in S3-compatible OTEL replay store with tenant-pinned object
  keys and JSONL fallback for local deployments.
- Added SHA-256 digests to sanitized replay records and object metadata for
  independent payload-integrity verification.
- Added a separately published `-analytics` GHCR OCI image for the Rust
  control plane; it is released independently from the gateway image and
  binary verification lane.
- Helm can now pin that analytics OCI image by validated `sha256` digest,
  keeping independently scaled control-plane rollouts reproducible.
- Added tenant-scoped durable queue metrics at `/metrics?tenant=<id>` and
  configurable Helm connection budgets, disruption protection, and autoscaling
  boundaries for analytics replicas.
- Added structured tenant queue stats at
  `GET /v1/jobs/stats?tenant=<id>` for operators and autoscalers; durable query
  failures return `503` rather than a misleading local snapshot.
- Added the isolated `analytics-rs` contract slice with versioned job
  submission, lease ownership, cancellation, terminal completion, and
  deterministic tests. It is not yet wired into the inference gateway.
- Added the dependency-free analytics contract operator check (`--check`) for
  deterministic submit/lease/complete verification.
- Added `make rust-test` and `make rust-clean`; the cleanup target uses
  `cargo-sweep` when available to bound local Rust build-artifact growth.

### Branding and compatibility

- Fork-facing benchmark, provider, virtual-key, pricing, skills, and enterprise
  fallback surfaces now link to FrankenGate-local routes; retained Bifrost
  package names and `x-bf-*` headers remain explicitly documented compatibility
  inputs.
- Updated the Helm chart README to identify FrankenGate as the fork-owned
  product while documenting the retained `bifrost.*` chart/value identifiers.
- Rebranded the UI README and its documentation links to FrankenGate-owned
  surfaces; the `BIFROST_PORT` environment variable remains a documented
  compatibility input for now.
- Added `scripts/audit-fork-branding.sh` to separate fork-facing upstream URLs
  from inherited compatibility identifiers before stable-release publication.
- Removed the unsupported upstream Artifact Hub badge from the fork README;
  stable FrankenGate Artifact Hub publication is still pending.

### Known limitations

- Governance request admission still uses pod-local budget counters; atomic
  cross-replica PostgreSQL reservations are tracked separately from the
  analytics worker queue.
- Synchronization metrics and a complete external Redis contract remain planned.

## 0.3.10

Released 2026-07-20 from the verified `dev` baseline.

### Release verification

- Stable release artifact selection now uses the fork-owned artifact glob.
- Go correctness checks no longer depend on the stalled hosted cache service.
- GitHub Dependency Review is enabled and passing for the fork.
- The Rust analytics contract suite passes all 15 deterministic lifecycle tests.

This patch release does not claim PostgreSQL-backed analytics persistence or
production GHCR image equivalence; those remain tracked as open beads.

## 0.3.9

This tag contains the release candidate at `0fb398454364426a23fb643f78c4bb101c069aaf`.

### Compatibility

- Patch-level release candidate. No config schema migration is claimed by this
  entry; verify the chart and image digests before promotion.
- The Helm replacement proof exercises three replicas, upgrade, rollback, and
  re-upgrade with a retained virtual key. Publication evidence is authoritative
  only when the corresponding GitHub Actions run is successful.

### Verification scope

- Provenance and redistribution-policy self-tests.
- Multi-module compile, race, vet, vulnerability, chart, SBOM, and attestation
  gates as defined by the fork-owned workflows.
