# Release Baseline Gap Ledger

Audit owner: read-only release reproducibility audit for Bead `bif-kyy.14.1`
Date: 2026-07-15
Repo: `/Users/pierre/dev/bifrost`
Conclusion: do not claim release readiness. The current repository has useful release automation, but the complete binary/image/chart/source baseline is not yet reproducible or promotable for internal enterprise Kubernetes without P0 gates below.

## Bead Scope

`br show bif-kyy.14.1 --json` says the task is to reproduce the upstream build and map the complete release surface from a clean pinned checkout, including tests, binary/image/chart/source outputs, Go modules/tags, registries, CI secrets, signing, SBOM, source correspondence, Apache license/NOTICE/modification duties, Maxim URLs and branding, then produce a release gap ledger and stop rather than claiming readiness.

This audit was read-only. I did not build, test, publish, sign, commit, push, edit Beads, edit code, edit README, edit workflows, or edit branding.

## Commands Used

Read-only commands used for evidence:

```bash
br show bif-kyy.14.1 --json
git status --short
rg --files -g 'Makefile' -g 'go.work' -g 'go.mod' -g 'go.sum' -g '.github/workflows/**' -g 'Dockerfile*' -g '*Dockerfile*' -g 'docker/**' -g 'helm/**' -g 'charts/**' -g 'deployments/**' -g 'k8s/**'
rg --files -g 'LICENSE*' -g 'NOTICE*' -g 'COPYING*' -g 'THIRD*' -g '*license*' -g '*notice*' -g '*sbom*' -g '*SBOM*' -g '*goreleaser*' -g '.goreleaser*' -g 'cosign*' -g '*sign*'
rg -n '(^[A-Za-z0-9_.-]+:|release|goreleaser|checksum|sha256|cosign|sign|sbom|SLSA|provenance|version|ldflags|Docker|docker|image|helm|chart|OCI|registry|publish|tag|snapshot)' Makefile
rg -n '(release|goreleaser|checksum|sha256|cosign|sign|sbom|SLSA|provenance|version|ldflags|Docker|docker|image|helm|chart|OCI|registry|publish|tag|snapshot|secrets|permissions)' .github/workflows
rg -n '^(module|go |toolchain|replace|require \()' core/go.mod framework/go.mod transports/go.mod cli/go.mod plugins/*/go.mod
rg -n '\b(cosign|syft|grype|sbom|SBOM|CycloneDX|SPDX|slsa|SLSA|attest|attestation)\b' .github Makefile transports helm-charts npx cli core framework plugins scripts -g '!ui/node_modules/**' -g '!tmp/**' -g '!dist/**' -g '!core/internal/llmtests/scenarios/media/**'
rg -n '\b(sha256sum|shasum|checksum|\.sha256|sign|signature|provenance|attest)\b' .github/workflows .github/workflows/scripts Makefile npx cli/internal/update -g '*.yml' -g '*.sh' -g '*.js' -g '*.go'
rg -n '(COPY LICENSE|COPY NOTICE|/licenses|LICENSE|NOTICE)' transports/Dockerfile transports/Dockerfile.local transports/Dockerfile.redhat .dockerignore helm-charts/bifrost/Chart.yaml helm-charts/bifrost/values.yaml npx/bifrost/package.json npx/bifrost-cli/package.json
rg -n '(appVersion|version:|repository:|tag:|home:|sources:|maintainers:|icon:)' helm-charts/bifrost/Chart.yaml helm-charts/bifrost/values.yaml
for f in cli/version core/version framework/version plugins/*/version transports/version; do printf '%s: ' "$f"; tr -d '\n\r' < "$f"; printf '\n'; done
git ls-files go.work go.work.sum
```

Key file inspections used `nl -ba ... | sed -n '<range>p'` against the exact files cited below.

## Release Surface Inventory

### Go Modules And Version Files

- Main modules use `go 1.26.4`: `core/go.mod:3`, `framework/go.mod:3`, `transports/go.mod:3`, `cli/go.mod:3`, and all inspected plugin modules.
- No committed `go.work` or `go.work.sum`: `git ls-files go.work go.work.sum` returned no paths.
- Makefile workspace helper rewrites local workspace files and says they are not committed: `Makefile:1659-1689`.
- Version files from `for f in cli/version core/version framework/version plugins/*/version transports/version; ...`:
  - `cli/version`: `0.10.6`
  - `core/version`: `1.7.1`
  - `framework/version`: `1.5.1`
  - `transports/version`: `1.6.4`
  - plugin versions range from `0.1.27` to `1.6.28`
- `transports/go.mod:18-28` pins released core/framework/plugin module versions for transport builds.

### Binary Artifacts

- Main HTTP binary local build: `Makefile:322-381`.
- Main HTTP release binary builds: `.github/workflows/scripts/build-executables.sh:29-36` lists darwin/amd64, darwin/arm64, linux/amd64, linux/arm64, windows/amd64; `.github/workflows/scripts/build-executables.sh:92-118` builds them with `GOWORK=off`, `CGO_ENABLED=1`, `-trimpath`, and `-buildid=`.
- Main HTTP binaries are uploaded to R2: `.github/workflows/release-pipeline.yml:1596-1670`, `.github/workflows/release-pipeline.yml:1672-1736`, `.github/workflows/scripts/upload-to-r2.sh:66-75`.
- CLI binaries generate checksums: `.github/workflows/scripts/build-cli-executables.sh:47-54`.
- Migration CLI binaries generate checksums: `.github/workflows/scripts/build-bifrost-migration-cli-executables.sh:47-54`.
- Main HTTP binary release script does not generate `.sha256` files: `.github/workflows/scripts/build-executables.sh:92-118` has build commands only; the focused checksum search found checksum generation only for CLI and migration CLI release scripts.

### Docker Artifacts

- Makefile local Docker target builds `bifrost`, short SHA, and `latest`: `Makefile:436-441`.
- Docker release builds per-arch Docker Hub tags:
  - amd64: `.github/workflows/release-pipeline.yml:1865-1887`
  - arm64: `.github/workflows/release-pipeline.yml:1978-1999`
  - manifest: `.github/workflows/release-pipeline.yml:2011-2055`, `.github/workflows/scripts/create-docker-manifest.sh:22-44`
- UBI9 builds and manifest:
  - UBI9 amd64: `.github/workflows/release-pipeline.yml:2139-2162`
  - UBI9 arm64: `.github/workflows/release-pipeline.yml:2256-2279`
  - UBI9 manifest: `.github/workflows/release-pipeline.yml:2291-2335`, `.github/workflows/scripts/create-docker-manifest-ubi9.sh:19-39`
- GHCR mirroring is best-effort, not a release gate: `.github/workflows/release-pipeline.yml:1888-1897`, `.github/workflows/release-pipeline.yml:2001-2009`, `.github/workflows/scripts/create-docker-manifest.sh:46-82`, `.github/workflows/scripts/create-docker-manifest-ubi9.sh:41-72`.
- Dockerfiles pin base image digests: `transports/Dockerfile:2`, `transports/Dockerfile:20`, `transports/Dockerfile:54`, `transports/Dockerfile.redhat:2`, `transports/Dockerfile.redhat:20`, `transports/Dockerfile.redhat:52`.
- Dockerfiles also run mutable package updates during builds: `transports/Dockerfile:5-6`, `transports/Dockerfile:23-25`, `transports/Dockerfile:61-62`, `transports/Dockerfile.redhat:5-6`, `transports/Dockerfile.redhat:23-25`.

### Helm Artifacts

- Chart metadata: `helm-charts/bifrost/Chart.yaml:5-6` says chart version `2.1.28` and `appVersion: "1.5.12"`.
- Current transport version file is `transports/version:1` with `1.6.4`.
- Default image repository/tag: `helm-charts/bifrost/values.yaml:15-20` defaults to `docker.io/maximhq/bifrost` and empty tag.
- Helm index has chart digests for historical packages: `helm-charts/index.yaml:1-27`.
- Helm release workflow packages and publishes chart: `.github/workflows/helm-release.yml:97-110`.
- Helm index update and GitHub Pages publish: `.github/workflows/helm-release.yml:114-134`.
- Helm OCI pushes are best-effort: `.github/workflows/helm-release.yml:138-165` uses `continue-on-error: true` for registry logins and `helm push`.

### NPM/NPX Wrappers

- `npx/bifrost/package.json:2-19` publishes `@maximhq/bifrost` version `1.6.3`, Apache-2.0, author `Maxim HQ`.
- `npx/bifrost-cli/package.json:2-20` publishes `@maximhq/bifrost-cli` version `1.0.1`, Apache-2.0, author `Maxim HQ`.
- NPM workflow attempts trusted publishing with provenance, then falls back to token publish without provenance: `.github/workflows/npx-publish.yml:119-130`, `.github/workflows/npx-publish.yml:231-242`.
- Transport npx wrapper downloads binaries without checksum verification: `npx/bifrost/bin.js:190-242`, `npx/bifrost/bin.js:350-363`.
- CLI npx wrapper verifies checksums if checksum files exist, but skips verification if checksum file is unavailable or unparsable: `npx/bifrost-cli/bin.js:153-183`, `npx/bifrost-cli/bin.js:298-305`.

### Licensing And Notices

- Root `LICENSE` is Apache-2.0 and includes the NOTICE redistribution requirement: `LICENSE:89-121`.
- Root `NOTICE` exists and records FrankenGate provenance and modification notice: `NOTICE:1-14`.
- Red Hat image copies only `LICENSE`: `transports/Dockerfile.redhat:73-74`.
- Focused copy search found no `COPY NOTICE` in release Dockerfiles.
- Alpine release image does not copy `LICENSE` or `NOTICE`: `transports/Dockerfile:53-121`.
- NPM package directories contain only `bin.js`, `package.json`, and lockfile where present; `rg --files npx/bifrost npx/bifrost-cli` found no `LICENSE` or `NOTICE` in those package directories.

## Gap Ledger

### RBG-001 - Main transport binaries lack mandatory checksums and consumer verification

Severity: P0
Status: blocks release baseline

Evidence:

- `.github/workflows/scripts/build-executables.sh:92-118` builds `bifrost-http` artifacts but does not emit `.sha256` files.
- `.github/workflows/scripts/upload-to-r2.sh:66-75` uploads whatever is in `dist/` to R2 without a manifest or checksum verification gate.
- `npx/bifrost/bin.js:190-242` downloads the HTTP transport binary and marks it executable.
- `npx/bifrost/bin.js:350-363` executes the downloaded binary.
- Checksum generation exists for the CLI, proving the pattern is available: `.github/workflows/scripts/build-cli-executables.sh:52-54`.
- Checksum generation exists for migration CLI: `.github/workflows/scripts/build-bifrost-migration-cli-executables.sh:52-54`.

Impact:

The main gateway binary is the artifact most likely to be run by npx users and to seed Docker/image builds. Without per-platform checksums and mandatory verification, R2 object corruption, accidental overwrite, or compromised distribution cannot be detected by the wrapper or by release review.

P0 gate:

Before any internal release promotion, `build-executables.sh` must emit `bifrost-http.sha256` per platform, upload a versioned checksum manifest, and make `npx/bifrost/bin.js` fail closed on missing, unparsable, or mismatched checksums. The release job must verify uploaded R2 objects by downloading and comparing checksums before finalizing the GitHub release.

### RBG-002 - No required signing, SBOM, or SLSA-style provenance for binary/image/chart artifacts

Severity: P0
Status: blocks release baseline

Evidence:

- Focused command `rg -n '\b(cosign|syft|grype|sbom|SBOM|CycloneDX|SPDX|slsa|SLSA|attest|attestation)\b' ...` found no SBOM/signing tooling in release paths, only comments about buildx default provenance in `.github/workflows/scripts/create-docker-manifest.sh:18-19` and `.github/workflows/scripts/create-docker-manifest-ubi9.sh:16-17`.
- Docker build steps do not set or gate explicit `provenance`, `sbom`, signing, or attestation outputs: `.github/workflows/release-pipeline.yml:1877-1887`, `.github/workflows/release-pipeline.yml:1990-1999`, `.github/workflows/release-pipeline.yml:2151-2162`, `.github/workflows/release-pipeline.yml:2268-2279`.
- Helm release packages and publishes `bifrost-<version>.tgz` without signing or provenance: `.github/workflows/helm-release.yml:97-110`.
- Binary R2 upload script uploads `dist/` directly without signatures or SBOM: `.github/workflows/scripts/upload-to-r2.sh:66-75`.

Impact:

An internal enterprise Kubernetes baseline needs a verifiable chain from Git commit to binary, image, and chart. Current automation may produce buildx provenance implicitly for images, but there is no repository-level gate that verifies it, preserves it in a release manifest, or covers R2 binaries and Helm charts.

P0 gate:

Generate and publish SBOMs for each Go binary, Docker image, and Helm chart. Sign image digests, chart packages, checksum manifests, and SBOMs with an approved signing mechanism. CI must verify signatures and SBOM presence before pushing `latest`, publishing charts, or marking the release complete.

### RBG-003 - Source-to-artifact correspondence is not frozen before binary upload

Severity: P0
Status: blocks release baseline

Evidence:

- `release-bifrost-http-prep.sh` can mutate and push `transports/` during the release: `.github/workflows/scripts/release-bifrost-http-prep.sh:142-151`.
- Binary jobs pull latest branch state after prep: `.github/workflows/release-pipeline.yml:1636-1637`, `.github/workflows/release-pipeline.yml:1705-1706`.
- Binary upload happens before final tag creation: `.github/workflows/release-pipeline.yml:1596-1670`, `.github/workflows/release-pipeline.yml:1672-1736`, then `.github/workflows/release-pipeline.yml:1738-1783`.
- The final tag is created after binaries have already been uploaded: `.github/workflows/scripts/release-bifrost-http-finalize.sh:86-91`.
- GitHub release is created without attaching the R2 binaries or an artifact manifest: `.github/workflows/scripts/release-bifrost-http-finalize.sh:163-167`.

Impact:

The release process can build from a moving branch state and publish artifacts before the release tag exists. A reviewer cannot prove from the GitHub release alone which exact commit, module graph, UI lockfile, Dockerfile digest, and builder inputs produced each R2 object and image digest.

P0 gate:

Create a release source manifest before building anything. It must include immutable commit SHA, tag name, module versions, `go.sum` checksums, UI `package-lock.json` hash, Dockerfile hashes, builder image digests, workflow run ID, and intended artifact names. All binaries/images/charts must be built from that exact SHA or tag, and the final release must publish the manifest plus artifact checksums/digests.

### RBG-004 - Docker builds use digest-pinned bases but mutable package updates

Severity: P0
Status: blocks reproducible image baseline

Evidence:

- Base images are digest-pinned in the Alpine image: `transports/Dockerfile:2`, `transports/Dockerfile:20`, `transports/Dockerfile:54`.
- Base images are digest-pinned in the UBI9 image: `transports/Dockerfile.redhat:2`, `transports/Dockerfile.redhat:20`, `transports/Dockerfile.redhat:52`.
- The same Dockerfiles run mutable package repository operations: `transports/Dockerfile:5-6`, `transports/Dockerfile:23-25`, `transports/Dockerfile:61-62`, `transports/Dockerfile.redhat:5-6`, `transports/Dockerfile.redhat:23-25`.
- UBI9 runtime install is also resolved at build time: `transports/Dockerfile.redhat:68-71`.

Impact:

Digest-pinned base images are undermined by `apk upgrade` and unpinned package installs. Rebuilding the same commit at a later time can produce different layers, packages, vulnerabilities, and SBOM output.

P0 gate:

For release images, remove mutable upgrade behavior or pin package repositories/package versions through a recorded lock. The release manifest must record image base digests, package set, final image digest, and SBOM digest. Promotion must use image digests, not `latest` or version tags alone.

### RBG-005 - Helm chart metadata and deployment defaults are not tied to the release artifact set

Severity: P0
Status: blocks Kubernetes release baseline

Evidence:

- `helm-charts/bifrost/Chart.yaml:5-6` says chart version `2.1.28` and app version `1.5.12`.
- `transports/version:1` says transport version `1.6.4`.
- `helm-charts/bifrost/values.yaml:15-20` defaults to Docker Hub and an empty image tag.
- Dependency images in chart values are tag-based rather than digest-pinned, for example Postgres `16-alpine` at `helm-charts/bifrost/values.yaml:1348-1349`, Weaviate `1.24.1` at `helm-charts/bifrost/values.yaml:1412-1413`, Redis `7.2.0-v20` at `helm-charts/bifrost/values.yaml:1469-1470`, and Qdrant `v1.16.0` at `helm-charts/bifrost/values.yaml:1512-1513`.
- Helm OCI pushes are best-effort: `.github/workflows/helm-release.yml:138-165`.

Impact:

Kubernetes operators cannot reconstruct which gateway image digest a chart release deploys. `appVersion` is stale relative to `transports/version`, image tag is intentionally required but not encoded by the chart release, dependency images are mutable tags, and OCI chart publication is not a required gate.

P0 gate:

For internal release baselines, produce a Helm values lock or chart release manifest that binds chart version, app version, gateway image digest, dependency image digests, config schema version, and chart package digest. Do not promote a chart unless packaged chart digest, OCI push, and GitHub release artifact all match the manifest.

### RBG-006 - Apache LICENSE/NOTICE obligations are not consistently carried into object artifacts

Severity: P0
Status: blocks distribution baseline until legal owner accepts or fixes

Evidence:

- Apache redistribution requirements include retaining NOTICE content when present: `LICENSE:89-121`.
- Root `NOTICE` exists and records fork provenance and modification notices: `NOTICE:1-14`.
- Red Hat Docker image copies only `LICENSE`: `transports/Dockerfile.redhat:73-74`.
- Focused command `rg -n '(COPY LICENSE|COPY NOTICE|/licenses|LICENSE|NOTICE)' ...` found no `COPY NOTICE` in release Dockerfiles.
- Alpine release Dockerfile does not copy either `LICENSE` or `NOTICE`: `transports/Dockerfile:53-121`.
- `rg --files npx/bifrost npx/bifrost-cli` found no `LICENSE` or `NOTICE` files in the npm package directories.

Impact:

Source distribution has the right top-level files, but binary, image, npm, and chart artifacts do not consistently include the notice material. That is a release blocker for an internal fork that plans to redistribute binaries/images/charts.

P0 gate:

Every object artifact must include `LICENSE`, `NOTICE`, and a generated third-party notice/license inventory where applicable. Docker images should carry them under a standard path, npm packages should include them in the package tarball, and Helm chart packages should include license/notice material or point to an included artifact manifest accepted by legal review.

### RBG-007 - Binary version metadata is incomplete and inconsistent across artifacts

Severity: P1
Status: must fix before claiming reproducibility; can be sequenced after P0 artifact gates

Evidence:

- HTTP binary has only `main.Version`; default is `v1.0.0` when unset: `transports/bifrost-http/main.go:76-104`.
- Makefile local build defaults `VERSION ?= dev-build`: `Makefile:13`.
- Makefile CLI build hard-codes a dev version: `Makefile:384-388`.
- CLI has `version` and `commit`: `cli/main.go:13-16`, `cli/main.go:37-39`.
- CLI release passes version and commit: `.github/workflows/scripts/release-cli.sh:26-30`.
- HTTP release binary build passes version but not commit/source date: `.github/workflows/scripts/build-executables.sh:92-118`.
- Helm chart `appVersion` does not match transport version: `helm-charts/bifrost/Chart.yaml:5-6` vs `transports/version:1`.
- NPM wrapper version is independent: `npx/bifrost/package.json:2-19`.

Impact:

An operator inspecting a running binary/image/chart cannot reliably map it to source commit, release manifest, or Helm chart. This slows incident response and weakens artifact correspondence.

Gate:

Add consistent runtime metadata for version, commit SHA, build date or source date, dirty state, module manifest digest, and release manifest digest. The `/health` or version endpoint and CLI/version command should expose the same identifiers.

### RBG-008 - Verification steps contain misleading or best-effort gates

Severity: P1
Status: fix before relying on release automation as a control

Evidence:

- `verify-bifrost-http-release.sh` checks tag `transports/bifrost-http/v${VERSION}`: `.github/workflows/scripts/verify-bifrost-http-release.sh:26-34`.
- The actual transport release tag is `transports/v${VERSION}`: `.github/workflows/scripts/release-bifrost-http-finalize.sh:13-15`, `.github/workflows/scripts/release-bifrost-http-finalize.sh:86-91`.
- Docker jobs run the verification script with `continue-on-error: true`: `.github/workflows/release-pipeline.yml:1840-1847`, `.github/workflows/release-pipeline.yml:1953-1960`, `.github/workflows/release-pipeline.yml:2114-2121`, `.github/workflows/release-pipeline.yml:2231-2238`.
- Admin `workflow_dispatch` can set `skip_tests`; release conditions accept skipped tests: `.github/workflows/release-pipeline.yml:50-65`, `.github/workflows/release-pipeline.yml:1182-1198`.
- Load performance test is explicitly non-blocking: `.github/workflows/release-pipeline.yml:855-870`.

Impact:

Some automation looks like a release gate but is either best-effort, skipped, or checking the wrong tag pattern. This is not inherently wrong for upstream velocity, but it is not sufficient for an enterprise reproducibility baseline.

Gate:

Create a separate internal release gate job that cannot be skipped by `--skip-ci` or admin `skip_tests`, verifies the correct tag/source manifest, and fails if any required artifact check is missing. Keep break-glass paths explicit, audited, and outside normal promotion.

### RBG-009 - NPM provenance is optional after fallback

Severity: P1
Status: fix if npm wrappers remain an internal install path

Evidence:

- `npx-publish.yml` grants `id-token: write` for provenance: `.github/workflows/npx-publish.yml:52-55`, `.github/workflows/npx-publish.yml:175-177`.
- Publish tries `npm publish --provenance`: `.github/workflows/npx-publish.yml:119-123`, `.github/workflows/npx-publish.yml:231-235`.
- If OIDC fails, it falls back to `NPM_TOKEN` publish without `--provenance`: `.github/workflows/npx-publish.yml:126-130`, `.github/workflows/npx-publish.yml:238-242`.

Impact:

The package may be published without provenance while the workflow still succeeds. If internal users install through npm/npx, this weakens source-to-package verification.

Gate:

Require provenance for npm wrapper publication or explicitly mark token fallback as non-release/non-promotable. Include npm package digest and provenance URL in the release manifest.

## P0 Gates Before Internal Promotion

1. Immutable source manifest gate.
   Required command shape: build from a clean checkout at the release SHA or tag, not from a mutable branch pull. The manifest must include commit SHA, tags, version files, module graph hash, UI lockfile hash, Dockerfile hashes, workflow run ID, and artifact names.

2. Main transport checksum gate.
   Required files: `.sha256` for every `bifrost-http` binary under each R2 platform path, plus one signed checksum manifest. Required consumer change before promotion: `npx/bifrost/bin.js` must fail closed on missing or mismatched checksum.

3. Signing and SBOM gate.
   Required outputs: signed image digests, signed Helm chart package, signed binary checksum manifest, SBOM per binary/image/chart, and CI verification before any `latest` or stable tag update.

4. Docker reproducibility gate.
   Required state: no mutable package upgrade/install resolution without a recorded lock; final promoted image references must be digests. Version tags are aliases only.

5. Helm release lock gate.
   Required state: chart version, appVersion, gateway image digest, dependency image digests, chart package digest, and config schema version all match a release manifest. OCI chart publication cannot be best-effort for the internal baseline.

6. License/NOTICE gate.
   Required state: every distributed source, binary, image, npm, and chart artifact includes or carries reviewed `LICENSE`, `NOTICE`, third-party notices, and modification provenance.

## Suggested Exact Repro Baseline Command Set

These commands are proposed gates, not commands run during this audit:

```bash
git clone <approved-repo-url> bifrost-release-checkout
cd bifrost-release-checkout
git checkout <release-sha-or-tag>
git status --short
```

```bash
GOWORK=off go env GOVERSION GOOS GOARCH CGO_ENABLED
cd core && GOWORK=off go mod verify
cd ../framework && GOWORK=off go mod verify
cd ../transports && GOWORK=off go mod verify
cd ../cli && GOWORK=off go mod verify
```

```bash
cd <repo>
make build-ui
bash ./.github/workflows/scripts/build-executables.sh "$(tr -d '\n\r' < transports/version)" "darwin/amd64 darwin/arm64 linux/amd64 linux/arm64 windows/amd64"
find dist -type f -maxdepth 3 -print | sort
sha256sum dist/*/*/bifrost-http* > dist/bifrost-http.SHA256SUMS
```

```bash
docker buildx build \
  --file transports/Dockerfile \
  --build-arg VERSION="$(tr -d '\n\r' < transports/version)" \
  --platform linux/amd64,linux/arm64 \
  --provenance=true \
  --sbom=true \
  --tag <internal-registry>/bifrost:v$(tr -d '\n\r' < transports/version) \
  .
```

```bash
helm lint helm-charts/bifrost
helm template bifrost helm-charts/bifrost --set image.tag=v$(tr -d '\n\r' < transports/version)
helm package helm-charts/bifrost
sha256sum bifrost-*.tgz
```

## Stop Conditions

Stop and do not promote if any of these are true:

- Any `bifrost-http` binary lacks a checksum.
- The npx wrapper can execute a downloaded gateway binary without verification.
- Any Docker image or Helm chart lacks SBOM/signature/provenance accepted by the internal policy.
- The release manifest cannot map every artifact digest back to one source SHA.
- Helm `appVersion`, image digest, and transport version disagree without an explicit compatibility note.
- LICENSE/NOTICE material is absent from any distributed artifact family.
- A workflow uses best-effort publication for a required internal registry target.

## Residual Non-P0 Work

- Decide whether upstream Maxim/H3/Bifrost package names, chart metadata, maintainers, URLs, and author fields remain acceptable for the internal fork. Evidence includes `helm-charts/bifrost/Chart.yaml:13-19`, `npx/bifrost/package.json:2-19`, `npx/bifrost-cli/package.json:2-20`, and `NOTICE:7-14`. This audit records the gap only; it does not edit branding.
- Decide whether `flake.nix` is part of the release surface. It pins nixpkgs through `flake.lock:3-16` but hard-codes package version `1.4.9` at `flake.nix:65`.
- Decide whether the public R2/npm/DockerHub/GHCR release paths are retained for internal releases or mirrored into a private registry/bucket with independent signatures.
