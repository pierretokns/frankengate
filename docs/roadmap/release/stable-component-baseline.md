# Stable Component Baseline

Date: 2026-07-15
Bead: `bif-kyy.1.2`
Auditor: Codex
Scope: select and evidence a stable component baseline. This document is the only roadmap/product file edited for this bead.

## Baseline Decision

Selected baseline: current committed source `f72747b1920aff11d42db170bdaccbd16c495fd8` on branch `dev`, compared against the fork release tag `v0.1.0` and independently tagged upstream component modules.

This is an enterprise planning baseline, not a release-green claim. It is deliberately selected because it is the current integration point for the enterprise governance primitives, and because practical non-secret build/test/benchmark evidence was collected from a clean source archive of this commit.

Publish readiness is still blocked by the gates in "Release Gates" below. The previous release audit in `docs/roadmap/release/bif-kyy-14-1-release-audit.md` remains useful, but it audited `73ca947775bc39fa125365bf4c88ddf8ff3caa8f`. This baseline independently re-ran evidence for the newer commit `f72747b1920aff11d42db170bdaccbd16c495fd8`.

## Source Facts

Commands run from `/Users/pierre/dev/bifrost` unless otherwise stated.

| Fact | Evidence |
|---|---|
| Current commit | `git rev-parse HEAD` -> `f72747b1920aff11d42db170bdaccbd16c495fd8` |
| Current branch | `git rev-parse --abbrev-ref HEAD` -> `dev` |
| Current describe | `git describe --tags --always --dirty` -> `v0.1.0-1-gf72747b19-dirty` |
| Head commit subject | `feat: add enterprise governance primitives` |
| Fork baseline tag | `v0.1.0` -> `73ca947775bc39fa125365bf4c88ddf8ff3caa8f`, `feat: launch FrankenGate compatibility baseline` |
| Remotes | `origin=https://github.com/pierretokns/frankengate.git`; `upstream=https://github.com/maximhq/bifrost.git` |
| Worktree at audit time | Dirty outside this file: `.beads/issues.jsonl`, existing release audit, and other untracked/modified roadmap/core files. Evidence runs used a clean archive. |
| Clean archive | `tmpdir=$(mktemp -d /tmp/bifrost-stable-baseline.XXXXXX)` -> `/tmp/bifrost-stable-baseline.BWp8fm`; `git archive --format=tar HEAD | tar -x -C "$tmpdir"` |
| `go.work` at committed HEAD | No `go.work` tracked at HEAD; `make setup-workspace` creates one in the clean archive for local-module builds. |

Delta from `v0.1.0` to HEAD:

```text
21 files changed, 7688 insertions(+), 13 deletions(-)
```

Notable paths in `git diff --name-status v0.1.0..HEAD` include new core governance/security packages, new roadmap architecture docs, and the existing release audit.

## Toolchain Baseline

| Surface | Version / Pin | Evidence |
|---|---:|---|
| Host Go binary | `go1.22.4 darwin/arm64` | `go version` |
| Go module directive | `go 1.26.5` in all 40 `go.mod` files | `find ... -name go.mod ... awk` |
| Go toolchain behavior | Patched to `go1.26.5` after Fork CI found reachable `GO-2026-5856` in `crypto/tls@go1.26.4` | Fork CI run `29416234643`; Go vulnerability database |
| Host Node | `v23.1.0` | `node -v` |
| Pinned local Node | `22.12.0` | `.nvmrc` and `make build` output |
| npm | `10.9.0` | `npm -v`; `make build` output under Node 22.12.0 |
| Make | `GNU Make 3.81` | `make --version` |
| Helm | `v3.19.0+g3d8990f` | `helm version --short` |
| Docker CLI | Podman-backed, not usable for builds in this shell | `docker build ...` failed to connect to Podman socket `127.0.0.1:60969` |
| Fork release workflow | Go `1.26.5`, Node `22.12.0` | `.github/workflows/frankengate-release.yml` |
| Maintained PR/release workflows | Go `1.26.5`; Node remains workflow-specific | `.github/workflows/*.yml` |
| Dockerfiles | Node `25-alpine3.23` and Go `1.26.5-alpine3.23` pinned by digest | `transports/Dockerfile*` |

Toolchain decision: require Go `1.26.5` throughout the maintained source,
workflow, Nix, and container surfaces. Go `1.26.4` is prohibited for release
because Fork CI proved a reachable standard-library TLS vulnerability. Use Node
`22.12.0` for fork release reproducibility because that is the fork release
workflow and `.nvmrc` pin. Treat Node `25` Dockerfile pins as a separate
release-surface divergence requiring an explicit decision.

## Component Tag Comparison

Latest stable tags were selected by fetched Git tags, excluding prerelease strings (`prerelease`, `alpha`, `beta`, `rc`) except where noted. `changed_files` is `git diff --name-only <tag>..HEAD -- <path> | wc -l`.

| Component | Current version file/package | Latest stable tag used for comparison | Path delta at HEAD | Baseline decision |
|---|---:|---|---:|---|
| Fork repo | `v0.1.0-1-gf72747b19` | `v0.1.0` | 21 repo files | Select HEAD for enterprise planning; not a publish tag. |
| `core` | `1.7.1` | `core/v1.7.1` | 6 files | HEAD contains new core packages after the latest tag; release requires new module tag/version decision. |
| `framework` | `1.5.1` | `framework/v1.5.1` | 0 files | Tag-clean; use `framework/v1.5.1` as stable baseline. |
| `transports` | `1.6.4` | `transports/v1.6.4` | 6 files | HEAD contains transport changes after latest stable tag; release requires new tag/version decision. |
| `cli` | `0.10.6` | `cli/v0.10.6` | 0 files | Tag-clean; use `cli/v0.10.6`. |
| `scripts/bifrost-migration-cli` | `0.1.0` | `bifrost-migration-cli/v0.1.0` | 2 files | Not tag-clean; release requires explicit migration CLI decision. |
| `plugins/compat` | `0.1.27` | `plugins/compat/v0.1.27` | 0 files | Tag-clean. |
| `plugins/governance` | `1.6.5` | `plugins/governance/v1.6.5` | 0 files | Tag-clean. |
| `plugins/jsonparser` | `1.5.28` | `plugins/jsonparser/v1.5.28` | 0 files | Tag-clean. |
| `plugins/logging` | `1.6.1` | `plugins/logging/v1.6.1` | 0 files | Tag-clean. |
| `plugins/maxim` | `1.6.28` | `plugins/maxim/v1.6.28` | 0 files | Tag-clean. |
| `plugins/mocker` | `1.5.28` | `plugins/mocker/v1.5.28` | 0 files | Tag-clean. |
| `plugins/modelcatalogresolver` | `1.0.9` | `plugins/modelcatalogresolver/v1.0.9` | 0 files | Tag-clean. |
| `plugins/otel` | `1.4.0` | `plugins/otel/v2.0.1` exists; `plugins/otel/v1.4.0` matches branch | 14 files vs `v2.0.1`; 0 vs `v1.4.0` | Deliberately hold baseline at branch-local `v1.4.0`; do not silently absorb `v2.0.1`. |
| `plugins/prompts` | `1.0.28` | `plugins/prompts/v1.0.28` | 0 files | Tag-clean. |
| `plugins/semanticcache` | `1.5.28` | `plugins/semanticcache/v1.5.28` | 0 files | Tag-clean. |
| `plugins/telemetry` | `1.5.28` | `plugins/telemetry/v1.5.28` | 0 files | Tag-clean. |
| `npx/bifrost` | `1.6.3` | `npx/bifrost/v1.6.3` | 0 files | Tag-clean. |
| `npx/bifrost-cli` | `1.0.1` | `npx/bifrost-cli/v1.0.1` | 0 files | Tag-clean. |
| Helm chart | `2.1.29`, appVersion `1.5.12` | `helm-chart-v2.1.28` | 7 files | Chart version is bumped but not tagged; release requires chart tag and destination decision. |

Exact changed files after latest stable tags:

```text
core/v1.7.1..HEAD -- core:
A core/admission/admission.go
A core/admission/admission_test.go
A core/mcpownership/ownership.go
A core/mcpownership/ownership_test.go
A core/privacy/privacy.go
A core/privacy/privacy_test.go

transports/v1.6.4..HEAD -- transports:
M transports/bifrost-http/handlers/health.go
A transports/bifrost-http/handlers/health_test.go
M transports/bifrost-http/handlers/middlewares.go
M transports/bifrost-http/handlers/middlewares_test.go
M transports/bifrost-http/main.go
M transports/changelog.md

helm-chart-v2.1.28..HEAD -- helm-charts/bifrost:
M helm-charts/bifrost/Chart.yaml
M helm-charts/bifrost/README.md
M helm-charts/bifrost/templates/deployment.yaml
M helm-charts/bifrost/templates/stateful.yaml
M helm-charts/bifrost/values-examples/providers-and-virtual-keys.yaml
M helm-charts/bifrost/values.schema.json
M helm-charts/bifrost/values.yaml
```

## Build/Test/Benchmark Evidence

All practical evidence below was collected from clean archive `/tmp/bifrost-stable-baseline.BWp8fm`, not the dirty worktree.

### Build Evidence

| Command | Result | Exact evidence |
|---|---:|---|
| `make setup-workspace` | PASS | Created local workspace; output included `✓ Go workspace ready with all local modules`; auto-switched to `go1.26.5`. |
| `make build LOCAL=1 DYNAMIC=1 VERSION=baseline-f72747b` | PASS | Node `v22.12.0`, npm `10.9.0`; `added 574 packages, and audited 575 packages in 5s`; `found 0 vulnerabilities`; `vite v8.0.16`; `✓ built in 1.13s`; `tsc --noEmit`; `Built: tmp/bifrost-http (version: vbaseline-f72747b)`. |
| `./tmp/bifrost-http -version` | PASS | `FrankenGate vbaseline-f72747b (derived from Bifrost)`; also logged `maxprocs: Leaving GOMAXPROCS=24: CPU quota undefined`. |
| `file tmp/bifrost-http` | PASS | `Mach-O 64-bit executable arm64`. |
| `shasum -a 256 tmp/bifrost-http` | PASS | `666535a9b68c19afd137c694e6bc338e759188932508a985c2aa9ba65cfe3f65`. |
| `du -h tmp/bifrost-http` | PASS | `111M`. |

### Test Evidence

| Command | Result | Exact evidence |
|---|---:|---|
| `GOWORK=off go test ./network ./schemas ./mcp ./providers/utils` from `core` | PASS | `core/network 30.289s`; `core/schemas 0.519s`; `core/mcp 0.454s`; `core/providers/utils 20.244s`. |
| `GOWORK=off go test ./bifrost-http/handlers ./bifrost-http/server` from `transports` | PASS | `handlers 7.155s`; `server 1.684s`. |
| `GOWORK=off go test ./...` from `plugins/governance` | PASS | `governance 7.052s`; `governance/complexity 0.579s`. |
| `GOWORK=off go test ./...` from `cli` | PASS | Test packages passed: `internal/harness 0.373s`, `internal/runtime 0.552s`, `internal/ui/logo 0.712s`, `internal/ui/tui 0.953s`, `internal/update 0.759s`; other CLI packages had no test files. |
| `GOWORK=off go test -race -v .` from `core/internal/mcptests`, before MCP test-server setup | FAIL | Missing setup/env evidence included `test-tools-server not found at .../examples/mcps/test-tools-server/dist/index.js`, `MCP_HTTP_URL not set`, and final failure `failed to connect MCP client TemperatureMCPServer ... context deadline exceeded`; package failed after `73.802s`. |
| `make setup-mcp-tests` | PASS | Built Go MCP servers and TypeScript servers; final `✓ All MCP test servers built`. |
| `GOWORK=off go test -race .` from `core/internal/mcptests`, after setup | PASS | `ok github.com/maximhq/bifrost/core/internal/mcptests 66.800s`. |
| `GOWORK=off go test ./...` from `framework` | FAIL | Many packages passed, including `configstore`, `logstore`, `migrator`, `modelcatalog`, `plugins`, `streaming`, and `tracing`; final failure was `framework/vectorstore` because local Pinecone `[::1]:5081`, Qdrant `[::1]:6334`, Redis `127.0.0.1:6379`, `6380`, `7100`, and Weaviate `127.0.0.1:9000` endpoints refused connections. |
| `helm lint helm-charts/bifrost` | PASS | `1 chart(s) linted, 0 chart(s) failed`; Helm also printed chart validation info: `image.tag is required`. |
| `helm template bifrost-baseline helm-charts/bifrost` | FAIL | Without image tag, template failed: `ERROR: image.tag is required`. |
| `helm template bifrost-baseline helm-charts/bifrost --set image.tag=vbaseline-f72747b` | PASS | Rendered `206` lines to temp output. |
| `docker build -f transports/Dockerfile.local -t bifrost-baseline:f72747b .` | FAIL | Local Docker command is Podman-backed and unavailable: `unable to connect to Podman socket: failed to connect: dial tcp 127.0.0.1:60969: connect: connection refused`. |

Secret-backed tests and publishing commands were not run. Exact no-secret evidence from the audit shell:

```text
OPENAI_API_KEY=MISSING
ANTHROPIC_API_KEY=MISSING
GEMINI_API_KEY=MISSING
AWS_ACCESS_KEY_ID=MISSING
AWS_SECRET_ACCESS_KEY=MISSING
MAXIM_API_KEY=MISSING
NPM_TOKEN=MISSING
DOCKER_USERNAME=MISSING
DOCKER_PASSWORD=MISSING
R2_ACCESS_KEY_ID=MISSING
R2_SECRET_ACCESS_KEY=MISSING
```

### Benchmark Evidence

Method used for this run:

- Clean archive of commit `f72747b1920aff11d42db170bdaccbd16c495fd8`.
- Local workspace set up before benchmarks.
- `GOWORK=off` for module-local benchmark commands.
- `-run '^$'` to avoid mixing tests into benchmark timing.
- `-benchmem -count=5` for repeat samples.
- Host reported by benchmark output: `goos: darwin`, `goarch: arm64`, `cpu: Apple M2 Ultra`.
- Governance benchmark required `-benchtime=1x` because its setup is intentionally outside the timer; default auto-calibration caused a runaway wall-time run and was terminated.

Core:

```text
GOWORK=off go test -run '^$' -bench 'BenchmarkCalculateBackoff|BenchmarkIsRateLimitError' -benchmem -count=5 .

BenchmarkCalculateBackoff-24: 7.312-7.419 ns/op, 0 B/op, 0 allocs/op
BenchmarkIsRateLimitError-24: 66.93-85.41 ns/op, 2-3 B/op, 0 allocs/op
PASS; ok github.com/maximhq/bifrost/core 16.819s
```

Framework streaming:

```text
GOWORK=off go test -run '^$' -bench BenchmarkBuildResponsesMessageTextDeltas -benchmem -count=5 ./streaming

BenchmarkBuildResponsesMessageTextDeltas-24: 51566-55053 ns/op, 114216 B/op, 33 allocs/op
PASS; ok github.com/maximhq/bifrost/framework/streaming 9.447s
```

Transport server:

```text
GOWORK=off go test -run '^$' -bench BenchmarkMarshalPluginConfig -benchmem -count=5 ./bifrost-http/server

BenchmarkMarshalPluginConfig_WithPointerType-24: 1.975-2.000 ns/op, 0 B/op, 0 allocs/op
BenchmarkMarshalPluginConfig_WithMap-24: 701.9-1039 ns/op, 436-474 B/op, 7 allocs/op
BenchmarkMarshalPluginConfig_WithString-24: 265.1-273.3 ns/op, 303-310 B/op, 5 allocs/op
PASS; ok github.com/maximhq/bifrost/transports/bifrost-http/server 24.571s
```

Governance:

```text
GOWORK=off go test -run '^$' -bench BenchmarkSingleRequestTimeRateLimitResetDoesNotRefreshReferences -benchmem -benchtime=1x -count=5 .

BenchmarkSingleRequestTimeRateLimitResetDoesNotRefreshReferences-24:
4.809792-5.551833 ms/op, 7.913320-7.981320 MB/op, 113027-113093 allocs/op
PASS; ok github.com/maximhq/bifrost/plugins/governance 0.719s
```

## Repeatable Benchmark Methodology

1. Benchmark only from a clean archive or clean worktree at an exact commit.
2. Record host CPU, OS, architecture, Go toolchain behavior, and Node pin before any numbers.
3. Run `make setup-workspace` for local-module builds, then benchmark module-local packages with `GOWORK=off`.
4. Use `-run '^$' -bench <exact pattern> -benchmem -count=5`.
5. Use `-benchtime=1x` only for benchmarks that intentionally exclude heavy setup from `b.StartTimer`/`b.StopTimer`; otherwise the harness can inflate `b.N` and hide wall-clock setup cost.
6. Store raw benchmark output in the release evidence bundle and compare with `benchstat` on the same hardware class. Do not set hard release thresholds from this single laptop run.
7. Treat these numbers as regression sentinels for the named paths, not as whole-gateway throughput claims. No 5,000 RPS or provider-call benchmark was run here.

## Upstream Update Strategy

1. Fetch upstream tags before each baseline refresh: `git fetch --tags --all --quiet`.
2. For each independently tagged component, compare current path content against the latest stable tag, excluding prerelease tags unless a release explicitly opts into a prerelease track.
3. Use version files/package versions as the branch-local truth when they conflict with higher upstream stable tags. Example: `plugins/otel` stays at branch-local `v1.4.0`; `plugins/otel/v2.0.1` must be reviewed as an explicit upgrade, not silently pulled into this baseline.
4. For components with path deltas after their latest stable tag (`core`, `transports`, migration CLI, Helm), require a new tag/version decision before publication.
5. Re-run the evidence suite above after any upstream import or version bump.
6. Promote by protected Git merge request only. The gateway/agent may prepare issues, patches, and draft MRs, but must not merge, tag, publish, or push release assets.

## Release Gates

P0 gates before calling this publishable:

- Clean worktree or clean release branch containing only intended release changes.
- Resolve module version/tag decisions for `core`, `transports`, migration CLI, and Helm chart.
- Decide whether `plugins/otel` remains pinned to `v1.4.0` or explicitly upgrades to the `v2` line.
- Re-run framework vector-store tests with required local Pinecone, Qdrant, Redis, and Weaviate services, or split those integration tests behind explicit service gates.
- Run provider integration tests with approved non-production credentials.
- Run Docker image build in a working Docker/Podman environment; current shell cannot connect to Podman.
- Run Helm template/lint with the exact release image tag.
- Preserve checksums and add/verify signing/SBOM/provenance policy before any external release.

P1 gates:

- Align Node version policy across `.nvmrc`, fork release workflow, upstream workflows, and Dockerfiles.
- Add a reproducible benchmark artifact path and `benchstat` comparison in CI.
- Decide whether inherited upstream release destinations (`maximhq` Docker/Helm/npm/R2/GitHub release surfaces) are intentionally retained, disabled, or rebranded for the fork.

## Final Confidence

Evidence completeness for this bead: high. The document independently compares current commit `f72747b1920aff11d42db170bdaccbd16c495fd8` against fetched stable component tags, records toolchain versions, selects the branch-current enterprise planning baseline deliberately, runs non-secret build/test/benchmark commands, captures exact negative evidence, and defines repeatable benchmark and upstream-update methods.

Release readiness confidence: medium-low until the P0 gates are cleared.
