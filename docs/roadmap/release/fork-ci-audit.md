# Fork CI Audit

Status: First slice implemented for `bif-kyy.11.4`; broad release gate remains open.

Date: 2026-07-15

Scope: Public fork `pierretokns/frankengate`, inherited Bifrost workflows, and fork-owned CI required-check planning.

## GitHub Evidence

Recent fork failures are isolated to the inherited Snyk workflow:

- Run `29412673708`, `Snyk checks`, push to `dev`, failed on 2026-07-15: both `Snyk Code (SAST)` and `Snyk Open Source (deps)` failed at step `Install uv`.
- Failed log line: `Subscription is not valid. Reach out to support@stepsecurity.io`.
- The failure occurs in `step-security/setup-uv@ccf0a26ce9117d9e99292b0ce953ea5d9ffe778e` before `uv sync`, build, Snyk CLI setup, `snyk test`, `snyk code test`, or SARIF upload.
- Runs `29412273451` and `29391830341` show the same failed workflow class on the fork.

Conclusion: the fork was paying CI cost for an upstream/subscription-dependent workflow that did not reach the security scan.

## First Slice Implemented

Added `.github/workflows/fork-ci.yml` as the fork-owned PR/push/manual workflow:

- Pinned actions: `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd`, `actions/setup-go@4b73464bb391d4059bd26b0524d20df3927bd417`.
- Minimal default permission: `contents: read`.
- Concurrency cancellation by workflow/ref.
- Explicit job timeouts.
- No provider, Snyk, R2, npm, Docker Hub, Maxim, Codecov, or cloud secrets.
- `actions/setup-go` cache disabled; Go build/module caches are runner-temp only.
- Compile and vet coverage for `core`, `framework`, `transports`, and the
  fork-relevant plugin modules listed in
  `.github/workflows/scripts/fork-go-checks.sh`, plus uncached race tests for
  the current enterprise primitives and streaming package.
- Go vulnerability coverage through pinned `govulncheck@v1.1.4`.
- Provenance hook runs `scripts/verify-provenance.sh` when that script exists.

Removed `.github/workflows/snyk.yml` so automatic fork pushes no longer fail on
StepSecurity/Snyk subscription or upstream `SNYK_TOKEN` assumptions. Removed the
broken `.github/workflows/pr-test-notifier.yml`, which ran on `push` while
referencing a nonexistent pull-request payload. The inherited
`.github/workflows/release-pipeline.yml` was also removed: it was a 2,000-plus-
line upstream publisher coupled to provider secrets, Maxim/R2/npm/Docker
identities, external benchmarking, and broad release side effects. FrankenGate
tag publishing remains in the smaller fork-owned release workflow. These
removals do not claim equivalent Snyk SAST coverage.

## Security Coverage Replacement

Preserved immediately:

- `dependency-review.yml` continues to cover vulnerable dependency changes on pull requests.
- `dependabot-alerts.yml` continues to convert repository Dependabot alerts into issues.
- `scorecards.yml` continues supply-chain posture scanning.
- New `fork-ci.yml` adds `govulncheck` over the selected Go modules.
- The provenance hook keeps local provenance/license/notice checks in the fork CI path when present.

Not yet equivalent:

- Snyk Open Source all-project scanning is replaced only for Go modules by `govulncheck`; UI/npm, Python integration dependencies, container/image, and transitive non-Go coverage still need fork-owned replacements.
- Snyk Code SAST is not replaced in this slice. Candidate replacements are CodeQL, Semgrep, or a fork-owned Snyk subscription with no StepSecurity setup-uv dependency.

## Workflow Inventory

| Workflow | Current Classification | Rationale | Next Action |
|---|---|---|---|
| `dependabot-alerts.yml` | Keep | Uses GitHub API and `GITHUB_TOKEN`; no provider secrets. | Add timeout/concurrency and confirm issue-label behavior on the fork. |
| `dependency-review.yml` | Keep | Useful PR dependency security check with pinned action and minimal permissions. | Keep required for PRs after branch protection is aligned. |
| `docs-validation.yml` | Adapt | Docs-only check is useful, but `mintlify@latest` is not pinned and only runs on `main` docs pushes. | Pin Mintlify or containerize; add PR path if docs become required. |
| `e2e-tests.yml` | Manual | Branch-specific trigger and provider-secret assumptions. | Keep out of required fork CI until mock-provider E2E exists. |
| `frankengate-release.yml` | Keep | Fork-specific tag release path; no provider secrets in build jobs. | Audit release permissions and artifact provenance before making required. |
| `helm-release.yml` | Manual | Publishes chart/package from `main`; write permissions are real side effects. | Keep manual/release-only until chart ownership and rollback are tested. |
| `npx-publish.yml` | Manual | NPM publish/provenance side effects and registry ownership are not CI gates. | Keep release-only; verify fork package ownership before enabling. |
| `openapi-bundle.yml` | Adapt | Useful generated artifact check, but uses upstream-style `GH_TOKEN` and pushes from CI. | Split into PR validation and separate protected publish workflow. |
| `pr-test-notifier.yml` | Removed | Ran on push to `main` but referenced pull request context; not a useful fork gate. | Reintroduce only if a real PR-triggered notifier becomes necessary. |
| `pr-tests.yml` | Manual | Explicitly manual and provider-secret based; not suitable as required public-fork CI. | Keep for admin-triggered upstream-style live-provider testing only. |
| `release-bifrost-migration-cli.yml` | Manual | Release side effects and R2/GH token assumptions. | Keep manual until fork release credentials are designed. |
| `release-cli.yml` | Manual | Release side effects and R2/GH token assumptions. | Keep manual until fork release credentials are designed. |
| `release-pipeline.yml` | Removed | Upstream multi-artifact release pipeline with provider secrets, Codecov, Docker/R2 assumptions, and broad write behavior. | Port only proven reusable gates into small fork-owned workflows when prerequisites exist. |
| `scorecards.yml` | Keep | Useful supply-chain security workflow; no provider secrets. | Keep scheduled/main; verify code-scanning upload permissions on fork. |
| `snyk.yml` | Removed | Automatic Snyk scan failed before scanning due StepSecurity subscription and required upstream `SNYK_TOKEN`. | Replacement coverage starts in `fork-ci.yml`; add non-Go/SAST coverage before claiming parity. |
| `configs/docker-compose.yml` | Keep as support file | Not a workflow; supports inherited tests. | Audit when DB/UI/multipod gates are implemented. |
| `provenance.yml` | Keep if adopted | Present locally but outside this edit scope. | Not edited; `fork-ci.yml` runs the provenance script directly when present. |

## Required-Check Roadmap

Current first slice is not a complete replacement for the broad bead. The broad required-check target still needs real gates for:

- Aurora/PostgreSQL integration.
- UI build and Playwright without provider secrets.
- Multi-pod conformance.
- Helm render/schema validation.
- OpenAPI generated-artifact drift.
- DB migration compatibility.
- Release artifact verification, SBOM, signing, and provenance attestation.
- Non-Go dependency and SAST security coverage.

Broad inherited `go test ./...` is intentionally not relabeled as a unit gate:
it currently contains MCP suites that require built test servers and environment
URLs, framework suites that require PostgreSQL/Redis/vector databases, and at
least one provider regression (`providers/openai` GPT-OSS summary conversion).
The fork CI compiles those test binaries, runs focused secret-free race suites,
and leaves the service-backed and known-regression suites visible for their own
gates instead of silently skipping prerequisites or accepting a permanently red
required check.

Until those are implemented and passing on the public fork, `bif-kyy.11.4` should remain open.

## Local Validation

Performed in this workspace:

- `gh run view 29412673708 --log-failed` reproduced the StepSecurity subscription failure before Snyk scanning.
- `bash -n .github/workflows/scripts/fork-go-checks.sh` passed.
- Ruby YAML parsing passed for every `.github/workflows/*.yml` file present locally.
- `scripts/verify-provenance.sh --self-test` and `scripts/verify-provenance.sh` passed.
- `git diff --check` passed for the edited workflow/doc files.
- `actionlint` was not installed locally.
- `GOTOOLCHAIN=local .github/workflows/scripts/fork-go-checks.sh test-vet` stopped immediately because the local Go toolchain is `go1.22.4` and the repo requires `go >= 1.26.4`; the workflow installs Go `1.26.4`.
