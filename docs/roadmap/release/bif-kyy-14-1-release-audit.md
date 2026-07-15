# bif-kyy.14.1 Reproducible Release Audit

Date: 2026-07-15
Auditor: Codex
Bead: `bif-kyy.14.1`
Scope: reproducible release audit only. No code, workflow, README, release asset, or existing roadmap file was edited.

## Audit Result

Audit status: complete.

Release readiness status: not claimed. The local binary build reproduced from a clean archive of the pinned commit, and selected non-live tests were run, but several release surfaces remain unverified or blocked:

- `make test-mcp` failed in the Makefile harness because `gotestsum` was not found on `PATH` after installation.
- Direct MCP tests passed with `go test -race`.
- Direct `framework` module tests failed on missing local vector-store dependencies: Pinecone on `::1:5081`, Qdrant on `::1:6334`, Redis on `127.0.0.1:6379` / `6380` / `7100`, and Weaviate on `127.0.0.1:9000`.
- Live provider tests, Docker image builds, Helm publish, npm publish, GitHub release publishing, registry permissions, signing, SBOM generation, and CI secret availability were not executed.

## Source Correspondence

Original checkout:

- Repository: `/Users/pierre/dev/bifrost`
- Branch: `dev`
- Commit: `73ca947775bc39fa125365bf4c88ddf8ff3caa8f`
- `git describe --tags --always --dirty`: `v0.1.0-dirty`
- Remotes:
  - `origin`: `https://github.com/pierretokns/frankengate.git`
  - `upstream`: `https://github.com/maximhq/bifrost.git`

The original checkout was dirty during audit. To avoid touching tracked release assets or untracked product-code directories, reproduction was performed from a clean source archive:

```bash
tmpdir=$(mktemp -d /tmp/bifrost-release-audit.XXXXXX)
printf '%s\n' "$tmpdir"
git archive --format=tar HEAD | tar -x -C "$tmpdir"
```

Evidence:

```text
/tmp/bifrost-release-audit.5rsd9s
```

The archive is intentionally not a Git repository. It represents source content at commit `73ca947775bc39fa125365bf4c88ddf8ff3caa8f`, excluding dirty and untracked local worktree changes.

Important source facts:

- No `go.work` file exists in the archived HEAD. This differs from older AGENTS guidance that described a Go workspace file.
- 40 `go.mod` files exist in the source tree.
- Main modules and release modules use `go 1.26.4`.
- The local shell reports `go version go1.22.4 darwin/arm64`, but Go toolchain auto-switching occurred during tool installation.
- `.nvmrc` pins `22.12.0`; the shell had Node `v23.1.0`, while the Makefile build used Node `v22.12.0`.

## Command Evidence

Commands below were run from `/tmp/bifrost-release-audit.5rsd9s` unless otherwise noted.

| Command | Result | Exact evidence |
|---|---:|---|
| `make build` | PASS | `Node.js v22.12.0 and npm 10.9.0 are installed`; `added 574 packages, and audited 575 packages in 5s`; `found 0 vulnerabilities`; `vite v8.0.16 ... ✓ built in 1.09s`; `tsc --noEmit`; `Built: tmp/bifrost-http (version: vdev-build)` |
| `./tmp/bifrost-http -version` | PASS | `FrankenGate vdev-build (derived from Bifrost)` |
| `file tmp/bifrost-http` | PASS | `tmp/bifrost-http: Mach-O 64-bit executable arm64` |
| `shasum -a 256 tmp/bifrost-http` | PASS | `1cd6fa27b72f7b80eeb671abe4c69483f47f3615d75bb663498c0c7b88afce7b  tmp/bifrost-http` |
| `make test-mcp` | FAIL | Installed `gotestsum`, switched to `go1.25.12`, built all MCP test servers, then failed with `bash: gotestsum: command not found` and `make: *** [test-mcp] Error 1` |
| `GOWORK=off go test -race -v .` in `core/internal/mcptests` | PASS | Final lines: `PASS`; `ok  	github.com/maximhq/bifrost/core/internal/mcptests	67.395s`; output included skips for missing `MCP_HTTP_URL`, `MCP_SSE_URL`, and real LLM configuration |
| `GOWORK=off go test ./...` in `framework` | FAIL | Many package groups passed, including `configstore`, `logstore`, `migrator`, `modelcatalog`, `plugins`, `streaming`, and `tracing`; final failure was `github.com/maximhq/bifrost/framework/vectorstore` due missing local Pinecone/Qdrant/Redis/Weaviate endpoints |
| `GOWORK=off go test ./...` in `plugins/governance` | PASS | `ok  	github.com/maximhq/bifrost/plugins/governance	5.752s`; `ok  	github.com/maximhq/bifrost/plugins/governance/complexity	1.194s` |

Not executed:

- `make test-core`: provider integration tests require live provider API credentials and were not run.
- Docker image builds/pushes: not run to avoid registry writes and release asset mutation.
- Helm package/push: not run to avoid release asset mutation.
- npm publish: not run.
- GitHub release publication: not run.
- CI workflows: not dispatched.
- SBOM/signing/provenance verification against published artifacts: not run.

## Module And Tag Inventory

### Go modules

Command:

```bash
find . -path './.git' -prune -o -name go.mod -print | sort
```

Count: 40.

Release-relevant modules:

- `core/go.mod`: `module github.com/maximhq/bifrost/core`, `go 1.26.4`
- `framework/go.mod`: `module github.com/maximhq/bifrost/framework`, `go 1.26.4`
- `transports/go.mod`: `module github.com/maximhq/bifrost/transports`, `go 1.26.4`
- `cli/go.mod`: `module github.com/maximhq/bifrost/cli`, `go 1.26.4`
- `scripts/bifrost-migration-cli/go.mod`: `module github.com/maximhq/bifrost/scripts/bifrost-migration-cli`, `go 1.26.4`
- Plugin modules: `compat`, `governance`, `jsonparser`, `logging`, `maxim`, `mocker`, `modelcatalogresolver`, `otel`, `prompts`, `semanticcache`, `telemetry`; all sampled plugin `go.mod` files use `go 1.26.4`.

### Node packages

Command:

```bash
find . -path './.git' -prune -o -path '*/node_modules/*' -prune -o -name package.json -print | sort
```

Count: 14.

Release-relevant packages:

| File | Package | Version | Private | Bin |
|---|---|---:|---:|---|
| `ui/package.json` | `@maximhq/bifrost-ui` | `0.1.0` | true | none |
| `npx/bifrost/package.json` | `@maximhq/bifrost` | `1.6.3` | false | `bifrost` |
| `npx/bifrost-cli/package.json` | `@maximhq/bifrost-cli` | `1.0.1` | false | `bifrost` |
| `npx/bifrost-migration-cli/package.json` | `@maximhq/bifrost-migration-cli` | `0.1.0` | false | `bifrost-migration-cli` |
| `tests/e2e/package.json` | `@bifrost/e2e-tests` | `1.0.0` | true | none |
| `tests/integrations/typescript/package.json` | `bifrost-integration-tests-typescript` | `0.1.0` | false | none |

### Tags observed

Recent tags by creation time included:

- Fork/public baseline tag: `v0.1.0`
- Helm: latest observed tag by creation time `helm-chart-v2.1.28`; chart file currently says `version: 2.1.29`
- Core: latest observed `core/v1.7.1`
- Framework: latest observed `framework/v1.5.1`
- Transports: latest observed by creation time `transports/v1.6.4`; `transports/v2.0.0-prerelease1` also exists
- NPX: `npx/bifrost/v1.6.3`, `npx/bifrost-cli/v1.0.1`
- Plugins by creation time: `plugins/otel/v1.4.0`, `plugins/telemetry/v1.5.28`, `plugins/semanticcache/v1.5.28`, `plugins/prompts/v1.0.28`, `plugins/modelcatalogresolver/v1.0.9`, `plugins/mocker/v1.5.28`, `plugins/maxim/v1.6.28`, `plugins/logging/v1.6.1`, `plugins/jsonparser/v1.5.28`, `plugins/governance/v1.6.5`, `plugins/compat/v0.1.27`

## Release Surface Inventory

### Fork release workflow

File: `.github/workflows/frankengate-release.yml`

Observed behavior:

- Trigger: push tags matching `v*`.
- Builds matrix artifacts: `linux-amd64`, `darwin-arm64`, `darwin-amd64`.
- Pinned actions are used for harden-runner, checkout, setup-go, setup-node, upload/download artifacts.
- Go version is pinned to `1.26.4`; Node is pinned to `22.12.0`.
- Build step runs:
  - `make setup-workspace`
  - `make build LOCAL=1 DYNAMIC=1 VERSION="${VERSION#v}"`
  - `./tmp/bifrost-http -version`
- Package step creates `frankengate-${VERSION}-${ARTIFACT}.tar.gz` containing:
  - `frankengate` binary copied from `tmp/bifrost-http`
  - `LICENSE`
  - `NOTICE`
- Release step creates `SHA256SUMS` and publishes a GitHub release with `gh release create ... --verify-tag`.

Gaps:

- No SBOM generation found.
- No artifact signing found.
- Checksums exist for fork release artifacts, but checksums are not signatures.
- The local reproduction ran `make build` without the workflow's `LOCAL=1 DYNAMIC=1 VERSION=...` tuple, so it proves local buildability but not exact CI release artifact equivalence.

### Inherited upstream release surfaces

Files: `.github/workflows/release-pipeline.yml`, `.github/workflows/helm-release.yml`, `.github/workflows/npx-publish.yml`, `.github/workflows/release-cli.yml`, `.github/workflows/release-bifrost-migration-cli.yml`, `.github/workflows/scripts/*`.

Observed registries and destinations:

- Docker Hub image: `docker.io/maximhq/bifrost`
- GHCR mirror: `ghcr.io/${github.repository}` for Docker images
- Helm chart GitHub Releases: `helm-chart-v<version>`
- Helm chart GitHub Pages index: `https://maximhq.github.io/bifrost/helm-charts`
- Helm OCI GHCR: `oci://ghcr.io/maximhq/helm-charts`
- Helm OCI Docker Hub: `oci://registry-1.docker.io/maximhq`
- npm packages: `@maximhq/bifrost`, `@maximhq/bifrost-cli`, and local package `@maximhq/bifrost-migration-cli`
- R2/S3-style binary distribution paths: `s3://$R2_BUCKET/bifrost/...`, `s3://$R2_BUCKET/bifrost-cli/...`, `s3://$R2_BUCKET/bifrost-migration-cli/...`
- GitHub Releases for Go module tags and npm package tags.

Branding and source URLs in release surfaces still point substantially at upstream Bifrost/Maxim:

- Helm chart `name: bifrost`
- Helm chart `home: https://www.getmaxim.ai/bifrost`
- Helm chart `sources: https://github.com/maximhq/bifrost`
- Helm chart maintainer: `Bifrost Team <support@getbifrost.ai>`
- Helm chart icon: `https://www.getbifrost.ai/favicon.png`
- Helm values default image: `docker.io/maximhq/bifrost`
- Helm README and index URLs reference `github.com/maximhq/bifrost`, `maximhq.github.io/bifrost`, Docker Hub `maximhq/bifrost`, and Artifact Hub `bifrost`.
- README top-level title is `FrankenGate`, but it intentionally retains upstream compatibility text, upstream badges, and upstream quickstart commands using `@maximhq/bifrost` and `maximhq/bifrost`.

This is acceptable only if the release being audited is explicitly a compatibility baseline and not a fully rebranded distribution. It is not safe to publish inherited upstream workflows from the fork without deciding whether those destinations are intentionally retained, disabled, or renamed.

## CI Secrets And Permissions Inventory

Command:

```bash
rg -o "secrets\.[A-Z0-9_]+" .github/workflows .github/workflows/scripts -S | sed 's/.*secrets\.//' | sort -u
```

Secret names referenced by workflows/scripts:

```text
ANTHROPIC_API_KEY
AWS_ACCESS_KEY_ID
AWS_ARN
AWS_BEDROCK_ROLE_ARN
AWS_REGION
AWS_S3_BUCKET
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN
AZURE_API_KEY
AZURE_API_VERSION
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
AZURE_ENDPOINT
AZURE_TENANT_ID
BEDROCK_API_KEY
BIFROST_ENCRYPTION_KEY
CEREBRAS_API_KEY
CODECOV_TOKEN
COHERE_API_KEY
DISCORD_WEBHOOK
DOCKER_PASSWORD
DOCKER_USERNAME
ELEVENLABS_API_KEY
FIREWORKS_API_KEY
GEMINI_API_KEY
GH_TOKEN
GITHUB_TOKEN
GOOGLE_LOCATION
GROQ_API_KEY
HUGGING_FACE_API_KEY
MAXIM_API_KEY
MAXIM_LOG_REPO_ID
MCP_SSE_HEADERS
MISTRAL_API_KEY
NPM_TOKEN
OPENAI_API_KEY
OPENROUTER_API_KEY
PARASAIL_API_KEY
PERPLEXITY_API_KEY
R2_ACCESS_KEY_ID
R2_BUCKET
R2_ENDPOINT
R2_SECRET_ACCESS_KEY
REPLICATE_API_KEY
REPLICATE_OWNER
RUNWARE_API_KEY
RUNWAY_API_KEY
SARVAM_API_KEY
SCORECARD_TOKEN
SGL_API_KEY
SNYK_TOKEN
VERTEX_CREDENTIALS
VERTEX_GCS_BUCKET
VERTEX_GCS_PREFIX
VERTEX_PROJECT_ID
XAI_API_KEY
```

No `vars.*` references were found in workflows/scripts by the same scan.

Permission observations:

- Fork release workflow uses repository `github.token` with `contents: write` only in the release job.
- Inherited Docker/Helm/npm workflows use Docker Hub credentials, GitHub token/package permissions, R2 credentials, npm OIDC and `NPM_TOKEN` fallback, and many provider API secrets for integration tests.
- Secret existence and least-privilege scopes were not verified. GitHub settings were not inspected.

## Signing, SBOM, And Provenance

Observed:

- No files matching local SBOM/SPDX/CycloneDX naming were found.
- No `cosign`, `syft`, `grype`, or explicit SBOM generation command was found in workflows/scripts by text scan.
- `npx-publish.yml` grants `id-token: write` and runs `npm publish --provenance --access public` for `@maximhq/bifrost` and `@maximhq/bifrost-cli`, with fallback to `NPM_TOKEN` and plain `npm publish --access public`.
- Docker manifest scripts comment that `docker/build-push-action` default provenance creates an OCI image index containing a provenance attestation manifest, and they select platform image manifests by architecture to avoid confusing attestation manifests with platform manifests.
- Fork `frankengate-release.yml` generates `SHA256SUMS`, but no signing or SBOM.

Audit conclusion:

- npm provenance is configured for inherited npm publishing when OIDC succeeds; fallback token publishing may not carry provenance.
- Docker provenance may exist from build-push-action defaults in inherited Docker workflows, but this was not verified against actual pushed images.
- Fork GitHub tarball artifacts have checksums, not signatures, and no SBOM was found.

## Apache License, NOTICE, Modification, And Branding Duties

Files inspected: `LICENSE`, `NOTICE`, `README.md`.

Apache-2.0 duties relevant to this fork:

- Recipients must receive a copy of the Apache License.
- Modified files must carry prominent notices stating that changes were made.
- Source distributions must retain upstream copyright, patent, trademark, and attribution notices that apply.
- If a NOTICE file is included in the upstream work, derivative distributions must include a readable copy of applicable NOTICE attributions.
- Apache-2.0 does not grant permission to use upstream trade names, trademarks, service marks, or product names except as required to describe origin and reproduce NOTICE content.

Current local evidence:

- `LICENSE` contains Apache License 2.0.
- `NOTICE` identifies `FrankenGate`, says it is derived from `https://github.com/maximhq/bifrost`, retains upstream copyright/patent/trademark/attribution notices, states independence from Maxim AI/Bifrost maintainers, and says changed files are recorded in Git history and carry additional modification notices where appropriate.
- README begins with `# FrankenGate`, states it is built from Bifrost, and states enterprise roadmap items are not claimed complete until implementation and conformance gates pass.
- README retains upstream Bifrost badges, Docker/npm commands, and compatibility branding.

Unverified:

- I did not audit every modified file in Git history for prominent modification notices.
- I did not inspect published artifacts to confirm `LICENSE` and `NOTICE` inclusion outside the fork workflow's declared package step.
- I did not verify trademark clearance for remaining Bifrost/Maxim branding in Docker, npm, Helm, docs, badges, or URLs.

## Release Gap Ledger

| ID | Surface | Status | Evidence | Required next action |
|---|---|---:|---|---|
| R-01 | Clean pinned source | WARN | Original checkout was `v0.1.0-dirty`; reproduction used `git archive HEAD` to exclude dirty/untracked changes. | Release only from a clean tag checkout or CI checkout. Do not include local dirty state in source correspondence. |
| R-02 | Local binary build | PASS | `make build` completed and produced `tmp/bifrost-http`; binary reported `FrankenGate vdev-build`; SHA-256 recorded. | Reproduce exact release workflow tuple `make build LOCAL=1 DYNAMIC=1 VERSION=<tag>` in CI or local audit before claiming release artifact equivalence. |
| R-03 | Makefile MCP test harness | FAIL | `make test-mcp` built test servers, then failed with `bash: gotestsum: command not found`. | Fix or document `gotestsum` install/PATH behavior; re-run canonical Make target. |
| R-04 | Direct MCP tests | PASS WITH SKIPS | `GOWORK=off go test -race -v .` passed in `core/internal/mcptests`; several tests skipped because `MCP_HTTP_URL`, `MCP_SSE_URL`, or real LLM config was absent. | Keep pass evidence, but do not claim HTTP/SSE or real-LLM MCP coverage from this run. |
| R-05 | Framework tests | FAIL | `framework/vectorstore` failed because Pinecone/Qdrant/Redis/Weaviate endpoints were absent; many non-vectorstore packages passed. | Provide the required local services or split unit tests from integration tests; rerun before release readiness. |
| R-06 | Governance plugin tests | PASS | `plugins/governance` and `plugins/governance/complexity` passed directly. | Keep as partial evidence only; full plugin matrix was not run. |
| R-07 | Live provider integration tests | UNVERIFIED | Not run; provider API credentials were not verified. | Run canonical `make test-core` matrix in CI or a credentialed release audit environment. |
| R-08 | Docker images | UNVERIFIED | Inherited workflows push `docker.io/maximhq/bifrost` and mirror to GHCR; no local Docker build/push was run. | Decide fork image namespace; verify image build, tags, manifests, provenance, vulnerability scans, and pullability. |
| R-09 | Helm chart | WARN | Chart file says `version: 2.1.29`; latest observed Helm tag by creation time was `helm-chart-v2.1.28`; chart metadata still points to Bifrost/Maxim URLs and Docker image. | Decide whether Helm remains upstream-compatible or must be fork-branded; verify `helm lint`, package, index, OCI push, and install tests. |
| R-10 | npm packages | WARN | Inherited npm packages are `@maximhq/bifrost` and `@maximhq/bifrost-cli`; npm provenance exists when OIDC succeeds, with token fallback. | Decide whether fork publishes npm packages; avoid accidental publish to upstream scope; verify provenance for actual package version. |
| R-11 | R2/GitHub binary distribution | UNVERIFIED | Release scripts reference R2 buckets and GitHub Releases; credentials and bucket contents were not inspected. | Verify bucket paths, immutable versioned artifacts, latest alias policy, rollback, and checksums/signatures. |
| R-12 | SBOM | FAIL | No local SBOM/SPDX/CycloneDX files or generation workflow found. | Add and verify SBOM generation for source, Go modules, npm packages, binaries, and images before claiming supply-chain readiness. |
| R-13 | Signing | FAIL | Fork workflow emits `SHA256SUMS` only; no artifact signing found. | Add signing policy, preferably keyless Sigstore/cosign for images and release artifacts, or explicitly document unsigned artifacts. |
| R-14 | Apache/NOTICE duties | WARN | `LICENSE` and fork `NOTICE` exist and fork workflow packages them; full modified-file notice audit was not done. | Audit modified files and release artifacts for Apache 2.0 section 4 and trademark duties. |
| R-15 | Upstream URLs and branding | WARN | README and Helm retain upstream Max/Bifrost badges, URLs, registries, npm scopes, and chart metadata. | Classify each retained upstream reference as compatibility, attribution, or accidental branding; update only through approved docs/release work. |
| R-16 | CI secrets and permissions | UNVERIFIED | 54 unique `secrets.*` names found; scopes/existence were not verified. | Verify secret existence, least privilege, environment protection, and fork-safe disablement of inherited publish workflows. |

## Practical Release Interpretation

This audit supports only the following narrow claim:

> At commit `73ca947775bc39fa125365bf4c88ddf8ff3caa8f`, a clean source archive built a local Darwin/arm64 embedded-UI `bifrost-http`/FrankenGate binary with `make build`; direct MCP race tests and direct governance plugin tests passed in this environment.

This audit does not support any of these claims:

- The release is ready.
- Published Docker/Helm/npm/GitHub/R2 artifacts correspond to this source.
- All tests pass.
- Live provider compatibility is verified.
- CI secrets and registry permissions are correct.
- Release artifacts are signed.
- SBOMs exist.
- All Apache-2.0 modification notice and trademark duties are fully satisfied.

## Recommended Next Steps

1. Fix the `gotestsum` install/PATH issue or make the Makefile invoke the installed binary deterministically.
2. Add a reproducible release target that produces binaries, checksums, SBOMs, and signatures in a clean tree without relying on dirty local state.
3. Run framework vector-store integration tests with the required local services, or split them behind explicit integration-test flags so unit baselines are reproducible without external daemons.
4. Decide the fork release namespace for Docker, Helm, npm, GitHub releases, docs URLs, and badges before enabling inherited upstream publish workflows.
5. Add SBOM generation and artifact/image signing to the fork release workflow.
6. Run the credentialed provider, Docker, Helm, npm, and registry publish verification in protected CI, then append the exact evidence in a follow-up audit.
