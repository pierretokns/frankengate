# FrankenGate Branding Surface Audit

Status: read-only audit. No product files, README, Beads, workflows, remotes, or release artifacts were edited for this pass.

## Thesis

FrankenGate cannot be launched publicly by changing visible strings alone. The Bifrost and Maxim names are embedded in five different classes of surface: marketing/docs/UI assets, package and registry identities, install and release infrastructure, deployment configuration, and wire/API compatibility. The safe launch path is a deliberate split:

- Change public product, package, image, chart, domain, support, security, and docs surfaces to FrankenGate before any public release.
- Retain Bifrost and Maxim only where required for Apache-2.0 attribution, factual origin, factual compatibility, historical release notes, or the optional Maxim observability integration.
- Keep old `bifrost`, `BIFROST_*`, `x-bf-*`, `sk-bf-*`, `BifrostError`, and Go module/import identifiers as compatibility aliases until a major-version migration plan is proven.
- Defer broad internal symbol renames. The internal Go substrate is large and low-overhead; cosmetic renaming there has high merge and regression cost with little launch value.

Existing roadmap context already flags this: `docs/roadmap/base-repo-language-and-product-decision.md:110-113` says current release paths and module names are Maxim-coupled, and `docs/roadmap/base-repo-language-and-product-decision.md:168-174` says to clear GitHub, package registries, container registries, domains, and trademarks while preserving Apache-2.0 notices. This audit treats that as known context.

## Legal Guardrails

Apache-2.0 requires retention, not brand carryover. `LICENSE:97-104` requires modified files to carry notices and source distributions to retain copyright, patent, trademark, and attribution notices. `LICENSE:106-121` requires NOTICE content, if present, to be redistributed in an allowed place and not construed as changing the license. `LICENSE:138-141` does not grant use of trade names, trademarks, service marks, or product names except for reasonable/customary origin description and NOTICE reproduction.

Current fork notice text exists and is correctly framed as attribution, not endorsement: `NOTICE:4-10` says FrankenGate is derived from Bifrost and is not affiliated with or endorsed by Maxim AI or the Bifrost maintainers; `NOTICE:12-14` says Bifrost and Maxim names are used only for origin and compatibility. Keep this class of statement. Do not use Bifrost or Maxim as package owner, product owner, maintainer, support route, release source, or visual brand for FrankenGate.

Naming risk was not legally cleared in this audit. `docs/roadmap/base-repo-language-and-product-decision.md:176-179` notes possible naming/trademark risk around `Frankengate`/`FrankenGateway`; the latest requested public name is `FrankenGate`, so this report assumes that name but still recommends formal trademark clearance before release.

## Audit Coverage

Raw search after excluding generated UI bundles and temp output found about 46,916 matching lines across 2,147 files for `bifrost|maxim|getbifrost|getmaxim|maximhq`. Top-level file counts: docs 606, core 551, framework 165, tests 160, ui 142, transports 129, plugins 115, examples 111, terraform 65, helm-charts 46, cli 31, npx 5, nix 4, recipes 4, community 4, plus root docs/configs. This is why the audit groups surfaces instead of recommending blind global replacement.

Generated and historical files were inventoried but not counted as launch source of truth: `ui/out/**`, `transports/bifrost-http/ui/**`, docs changelogs, release archives, and tests should follow source changes or be retained as history rather than edited first.

Classification legend:

- `must-change`: visible or published FrankenGate surface that should not ship with Bifrost/Maxim ownership, support, package, image, or domain identity.
- `must-retain-for-attribution`: legal, provenance, historical, or third-party-product reference that must remain factual and non-endorsement.
- `compatibility alias`: old name should continue to work while a new FrankenGate spelling is introduced and documented.
- `defer`: not launch-visible, generated, test-only, historical, or too risky to rename before compatibility gates exist.

## Inventory

| ID | Surface | Evidence | Classification | Launch action |
|---|---|---|---|---|
| BR-001 | Root legal attribution | `LICENSE:97-121`, `LICENSE:138-141`, `LICENSE:189-201`; `NOTICE:1-14`; `docs/roadmap/provenance-ledger.md:1-23` | must-retain-for-attribution | Keep Apache-2.0 license, NOTICE, provenance ledger, upstream copyright, and non-endorsement language. Add modification notices to changed files as appropriate. |
| BR-002 | Root README product presentation | `README.md:1-22` currently has partial FrankenGate framing, but `README.md:24-306` still exposes upstream badges, npm, Docker, docs, Maxim links, and Bifrost copy | must-change plus must-retain-for-attribution | For public release, rewrite product copy and badges to FrankenGate while retaining a concise upstream attribution section. This audit did not edit README. |
| BR-003 | Security and conduct reporting | `SECURITY.md:5-16`, `SECURITY.md:54-88`; `CODE_OF_CONDUCT.md:61-63` | must-change | Replace Maxim/Bifrost security advisory URL and email addresses with FrankenGate-controlled reporting routes before public release. Retain upstream scope only as origin attribution if needed. |
| BR-004 | Public docs site identity | `docs/docs.json:3-10`, `docs/docs.json:29-38`, `docs/docs.json:49-52`, `docs/docs.json:1240-1245` | must-change | Rename docs site, logo paths, banner, GitHub links, demo link, enterprise link, and footer socials to FrankenGate-controlled locations. |
| BR-005 | Docs SEO/analytics/support domains | `docs/jsonLd.js:4-27`, `docs/googleTag.js:11-21`, `docs/supportWidget.js:1-3` | must-change | Replace `getmaxim.ai`, `bifrost.getmaxim.ai`, `getbifrost.ai`, Maxim analytics, and support widget scripts with FrankenGate-controlled domains or remove tracking. |
| BR-006 | Quickstart install commands | `docs/quickstart/gateway/setting-up.mdx:2-12`, `docs/quickstart/gateway/setting-up.mdx:19-53`, `docs/quickstart/gateway/setting-up.mdx:66-83`, `docs/quickstart/gateway/setting-up.mdx:109-126` | must-change plus compatibility alias | Publish FrankenGate npm/Docker commands first. Mention Bifrost commands only as compatibility aliases or migration notes. |
| BR-007 | Docs body copy and public links | Docs search found 8,569 matches across `.mdx`, `.md`, `.js`, and `.json`; high-signal examples include `docs/features/observability/default.mdx:569-607` and quickstart above | must-change except attribution/history/integration | Rewrite active docs pages to FrankenGate; retain Bifrost only for origin/compatibility and historical docs. Do not rewrite docs changelogs as if old releases were FrankenGate releases. |
| BR-008 | Maxim observability docs | `docs/features/observability/maxim.mdx:1-17`, `docs/features/observability/maxim.mdx:27-30`, `docs/features/observability/maxim.mdx:61-74`, `docs/features/observability/maxim.mdx:100-115`, `docs/features/observability/maxim.mdx:143-151` | must-retain-for-attribution plus compatibility alias | If the Maxim plugin remains, keep `Maxim` as a third-party integration name and avoid implying Maxim endorsement. Change surrounding product noun from Bifrost to FrankenGate. Keep old import/header examples only in compatibility blocks. |
| BR-009 | OpenAPI docs and wire schema names | `docs/openapi/openapi.json:9361-9400`, `docs/openapi/openapi.json:61810-61827`, `docs/openapi/openapi.json:61950-61972` | compatibility alias | Do not break `x-bf-*`, `sk-bf-*`, `BifrostError`, or `is_bifrost_error` on day one. Add FrankenGate aliases later only with conformance and clear precedence. |
| BR-010 | UI package identity | `ui/package.json:2-10`, `ui/package-lock.json:2-8` | must-change | Rename the private UI package/build labels and generated-copy target naming after deciding the binary/embed path. |
| BR-011 | UI shell, title, logos | `ui/index.html:7-13`; `ui/app/login/layout.tsx:30`; `ui/components/sidebar.tsx:1279-1281`, `ui/components/sidebar.tsx:1311-1314`, `ui/components/sidebar.tsx:1381-1398` | must-change | Replace title, preconnect domain, shell IDs/classes if public-facing, logo assets, image alts, release-note links, and all visible Bifrost branding. |
| BR-012 | UI external links and support flows | `ui/components/sidebar.tsx:115-138`, `ui/components/sidebar.tsx:141-157`, `ui/components/sidebar.tsx:949-961`; `ui/components/trialExpiryBanner.tsx:15-37` | must-change | Replace GitHub, report-bug, docs, Calendly, Maxim Evals, enterprise trial, and support email links with FrankenGate destinations. |
| BR-013 | UI fallback enterprise screens and help links | `ui/app/_fallbacks/enterprise/components/login/loginView.tsx:19-68`; search shows many `docs.getbifrost.ai` links in `ui/app/_fallbacks/enterprise/**` and `ui/app/workspace/**` | must-change | Replace product text and docs links on all public UI surfaces. If enterprise gates remain placeholders, they must not advertise Bifrost Enterprise as the owner. |
| BR-014 | UI local storage/cookie keys and TypeScript types | `ui/components/sidebar.tsx:88`; `ui/lib/hooks/useTimezonePreference.ts:8`; `ui/lib/store/apis/baseApi.ts:30-60`; `ui/lib/types/config.ts:451-548`; `ui/lib/types/logs.ts:453-456` | compatibility alias | Keep old storage/header/type shapes initially to avoid logging users out or breaking saved table state. Introduce FrankenGate keys with migration/read-old-write-new semantics. |
| BR-015 | UI assets and screenshots | File inventory found `.github/assets/bifrost-logo.png`, `docs/media/bifrost-logo*.png`, 40+ docs media files with `bifrost` in the filename, `ui/public/bifrost-logo*.webp`, `ui/public/bifrost-icon*.webp`, `ui/public/maxim-logo*.webp`, `ui/public/images/mcp-servers/maxim.png`; SVG text hits include `docs/media/ui-mcp-per-user-oauth-flow-*.svg` | must-change except Maxim integration assets | Regenerate product logos, icons, screenshots, and diagrams. Keep Maxim logos only on the Maxim integration surface with third-party attribution. |
| BR-016 | Built UI bundles | `ui/package.json:10` copies `ui/out` to `transports/bifrost-http/ui`; generated bundles were excluded from raw counts | defer | Do not hand-edit generated bundles. Rebuild after source UI/assets/docs changes; verify no Bifrost product branding remains in shipped bundle except aliases/attribution. |
| BR-017 | NPM gateway wrapper | `npx/bifrost/package.json:2-28`; `npx/bifrost/bin.js:9-17`, `npx/bifrost/bin.js:73-79`, `npx/bifrost/bin.js:87-95`, `npx/bifrost/bin.js:169-181`, `npx/bifrost/bin.js:264-326`, `npx/bifrost/bin.js:375` | must-change plus compatibility alias | Publish under a FrankenGate npm scope/name and download host. Keep `npx @maximhq/bifrost` only as an explicit compatibility/migration path if legally and operationally permitted. |
| BR-018 | NPM CLI wrapper | `npx/bifrost-cli/package.json:2-28`; `npx/bifrost-cli/bin.js:10`, `npx/bifrost-cli/bin.js:73-85`, `npx/bifrost-cli/bin.js:205-239`, `npx/bifrost-cli/bin.js:262-361` | must-change plus compatibility alias | Introduce `frankengate` CLI, install dir, docs, and downloads. Consider keeping `bifrost` command and `~/.bifrost` as aliases for one major release. |
| BR-019 | NPM migration CLI | `npx/bifrost-migration-cli/package.json:2-35`; `npx/bifrost-migration-cli/bin.js` uses `downloads.getmaxim.ai`, `bifrost-migration-cli`, `docs.getbifrost.ai`, and `~/.bifrost` | must-change plus compatibility alias | Rename public package and docs. Keep old env/command aliases only if migration tooling must target Bifrost-compatible APIs. |
| BR-020 | Go CLI binary text | `cli/go.mod:1`; `cli/main.go:9-10`, `cli/main.go:31-42`, `cli/main.go:55-57` | must-change plus compatibility alias | New CLI module/binary should say FrankenGate. Old `bifrost` command can remain as alias with deprecation warning. |
| BR-021 | Go module/import identity | `core/go.mod:1`; `framework/go.mod:1,10`; `transports/go.mod:1,18-28`; `plugins/governance/go.mod:1,11-12`; `plugins/maxim/go.mod:1,6-8`; imports in `transports/bifrost-http/main.go:66-71` | compatibility alias | Decide new module path. For launch, either keep old paths as compatibility modules or publish new modules with forwarding/deprecation docs. Do not blind-rewrite 551 core and 165 framework files without conformance. |
| BR-022 | Public exported Go symbols | `core/schemas/bifrost.go:22-39`, `core/schemas/bifrost.go:194-235`, `core/schemas/bifrost.go:1724-1776`; `core/schemas/context.go:49-68` | compatibility alias | `BifrostConfig`, `BifrostContext`, `BifrostStreamChunk`, and `BifrostError` are SDK-visible. Add FrankenGate aliases only after API compatibility decision. |
| BR-023 | HTTP runtime banner and env | `transports/bifrost-http/main.go:1-50`, `transports/bifrost-http/main.go:87-114`, `transports/bifrost-http/main.go:121-140`, `transports/bifrost-http/main.go:163` | must-change plus compatibility alias | Existing partial FrankenGate banner is not enough. Finish comments, logs, env docs, and URLs while keeping `BIFROST_HOST` as an alias. |
| BR-024 | Default app directories | `transports/bifrost-http/server/utils.go:14-47`; docs `docs/quickstart/gateway/setting-up.mdx:66-75` | compatibility alias | Introduce `~/.config/frankengate` and `%APPDATA%\\frankengate`, but keep reading old `bifrost` directories with explicit migration/precedence. |
| BR-025 | Config schema identity | `transports/config.schema.json:3-11`, `transports/config.schema.json:36-43`, `transports/config.schema.json:93-101` | must-change plus compatibility alias | New `$id`, title, description, and default schema URL must be FrankenGate-owned. `BIFROST_*` env names and `x-bf-*` header docs remain aliases until deprecation. |
| BR-026 | Config/env implementation | `transports/bifrost-http/lib/config.go:563`, `transports/bifrost-http/lib/config.go:905-915`, `transports/bifrost-http/lib/config.go:4168-4170` | compatibility alias | Add `FRANKENGATE_ENV_LABEL` and `FRANKENGATE_ENCRYPTION_KEY` before, or alongside, old `BIFROST_*` names. Do not remove old names in the compatibility release. |
| BR-027 | HTTP header contract | `transports/bifrost-http/lib/ctx.go:101-153`, `transports/bifrost-http/lib/ctx.go:250-305`, `transports/bifrost-http/lib/ctx.go:356-405`, `transports/bifrost-http/lib/ctx.go:522-580` | compatibility alias | Keep `x-bf-vk`, `x-bf-api-key`, `x-bf-dim-*`, `x-bf-mcp-*`, `x-bf-maxim-*`, raw capture, async, and compat headers. Add new aliases only with conflict rules and tests. |
| BR-028 | Docker image and labels | `transports/Dockerfile.redhat:57-64`; `examples/dockers/docker-compose.yml:1-4`; `transports/docker-entrypoint.sh:51-61` | must-change plus compatibility alias | Publish `frankengate` image under fork registry. Replace UBI labels, maintainer, examples, and public docs. Keep old env vars like `BIFROST_SKIP_WRITE_CHECK` as aliases. |
| BR-029 | Binary/embed path `bifrost-http` | `transports/Dockerfile.redhat:36-46`; `ui/package.json:10`; `nix/packages/bifrost-http.nix:34-80`; `npx/bifrost/bin.js:169-181` | compatibility alias | New binary name can be `frankengate-http`, but retain `bifrost-http` symlink or wrapper for compatibility and test harnesses. |
| BR-030 | Helm chart identity | `helm-charts/bifrost/Chart.yaml:1-19` | must-change plus compatibility alias | Public chart should be `frankengate` with fork home, sources, maintainers, support, icon. Keep old chart only as a compatibility chart or archive. |
| BR-031 | Helm values and chart schema | `helm-charts/bifrost/values.yaml:1-20`, `helm-charts/bifrost/values.yaml:89-123`, `helm-charts/bifrost/values.yaml:208-221`, `helm-charts/bifrost/values.yaml:335-350`, `helm-charts/bifrost/values.yaml:553-588`, `helm-charts/bifrost/values.yaml:1354`; `helm-charts/bifrost/values.schema.json:309,828` | must-change plus compatibility alias | Change defaults, examples, schema URLs, image repo, hostnames, and visible comments. Keep `.Values.bifrost` and `BIFROST_SCHEMA_URL` aliases for a deprecation window; introduce `.Values.frankengate`. |
| BR-032 | Helm templates and validation messages | `helm-charts/bifrost/templates/_helpers.tpl:204`, `helm-charts/bifrost/templates/_helpers.tpl:1246-1257`, `helm-charts/bifrost/templates/_helpers.tpl:1729-1733`, `helm-charts/bifrost/templates/deployment.yaml:6,101,201-206`, `helm-charts/bifrost/templates/stateful.yaml:5,97,197-202` | must-change plus compatibility alias | New rendered resources and errors should say FrankenGate. Keep `bifrost.plugins.maxim` only as compatibility alias and because Maxim is a real third-party plugin. |
| BR-033 | Helm repo/archive index | `helm-charts/index.yaml` repeatedly names `bifrost`, `getmaxim.ai`, `getbifrost.ai`, `github.com/maximhq/bifrost`, and `support@getbifrost.ai` | defer plus must-retain-for-attribution | Do not rewrite historical chart entries. Generate a new FrankenGate chart repo/index for new releases. |
| BR-034 | Terraform module identity | `terraform/modules/bifrost/README.md:1-15`, `terraform/modules/bifrost/variables.tf:22-35`, `terraform/modules/bifrost/variables.tf:149-169`, `terraform/modules/bifrost/variables.tf:290-293`, `terraform/modules/bifrost/main.tf:23-31` | must-change plus compatibility alias | New module source/path/defaults should be FrankenGate. Keep old module input defaults or aliases only if migration from Bifrost modules is supported. |
| BR-035 | Terraform resource names and examples | `terraform/modules/bifrost/kubernetes/main.tf:18-31`, `terraform/modules/bifrost/kubernetes/main.tf:69-119`, `terraform/modules/bifrost/kubernetes/main.tf:209-290`; `terraform/README.md:1-27,116-131` | compatibility alias plus defer | Terraform resource labels are stateful. Changing labels can force state migration. Public examples/docs must change, but module internals need a state migration plan. |
| BR-036 | Nix flake/modules/packages | `flake.nix:2,51-94`; `nix/modules/bifrost.nix:10-23`, `nix/modules/bifrost.nix:139-179`; `nix/packages/bifrost-http.nix:20-34,62-80`; `nix/packages/bifrost-ui.nix:7,25-26` | must-change plus compatibility alias | Publish new package/service names while keeping `services.bifrost` and `bifrost-http` aliases if Nix users are supported. |
| BR-037 | Release and publishing workflows | `.github/workflows/npx-publish.yml:113-161,225-297`; `.github/workflows/helm-release.yml:118-165`; `.github/workflows/release-pipeline.yml` includes `getbifrost.ai`, `downloads.getmaxim.ai`, `maximhq`, and `maxim-o1.openai.azure.com`; `.github/workflows/scripts/release-bifrost-http-finalize.sh:143-153` | must-change before use | Workflows must not publish to Maxim/GitHub/Docker/npm/Helm infrastructure for FrankenGate. This audit did not edit workflows. |
| BR-038 | Makefile release helpers | `Makefile:500-502`, `Makefile:1633`, `Makefile:1684-1687`, `Makefile:1828` | must-change plus defer | Release targets and docs references must move to FrankenGate. Test-only module checks can remain until module path migration. |
| BR-039 | GitHub ownership metadata | `.github/CODEOWNERS:1-8`; `.github/dependabot.yml:185`; `.github/workflows/snyk.yml:71,144` | must-change | Remove Maxim team/action ownership before public fork release. Keep no Maxim-owned required approvers or CI dependencies unless intentionally vendored and legally allowed. |
| BR-040 | Domain and registry names | Evidence spans docs, UI, installers, Helm, Terraform, workflows: `github.com/maximhq/bifrost`, `github.com/maximhq/bifrost-benchmarking`, `docs.getbifrost.ai`, `getbifrost.ai`, `www.getbifrost.ai`, `getmaxim.ai`, `www.getmaxim.ai`, `bifrost.getmaxim.ai`, `g.getmaxim.ai`, `downloads.getmaxim.ai`, `maximhq.github.io/bifrost`, `docker.io/maximhq/bifrost`, `ghcr.io/maximhq/helm-charts`, npm `@maximhq/*`, `calendly.com/maximai/bifrost-demo`, `support@getbifrost.ai`, `contact@getmaxim.ai`, `engineering@getmaxim.ai`, `akshay@getmaxim.ai`, `x.com/getmaximai`, `linkedin.com/company/maxim-ai` | must-change except attribution and optional Maxim integration links | Establish FrankenGate domains, registry orgs, email aliases, social links, docs, downloads, images, npm scope, GitHub org, and Helm repo. |
| BR-041 | Maxim plugin code and SDK dependency | `plugins/maxim/main.go:1-30`, `plugins/maxim/main.go:47-55`, `plugins/maxim/main.go:95-105`, `plugins/maxim/main.go:149-160`; `plugins/maxim/go.mod:1,6-8` | must-retain-for-attribution plus compatibility alias | Keep `Maxim` as third-party integration if feature is retained. Do not rename Maxim plugin to FrankenGate because it talks to Maxim SDK. Add docs caveat that Maxim is optional and external. |
| BR-042 | Plugin IDs and config keys | `plugins/maxim/main.go:22-25`; `ui/lib/types/plugins.ts:4`; `helm-charts/bifrost/templates/_helpers.tpl:1256`; `docs/features/observability/maxim.mdx:61-74` | compatibility alias | Keep plugin `name: "maxim"` for configs. If a generic observability plugin is introduced, add it separately rather than aliasing Maxim. |
| BR-043 | Database helper/function names | `framework/logstore/safe_jsonb_test.go:229-313`; `framework/configstore/vault_callbacks.go:35-37`; test DSNs at `framework/configstore/migrations_test.go:33` and `framework/logstore/migrations_test.go:18` | compatibility alias plus defer | DB functions/callback names and default test DB names are not product branding. Rename only with migrations if externally visible; otherwise defer. |
| BR-044 | Generated, test, and fixture surfaces | Tests count 160 matching files; examples count 111; `.github/workflows/configs/*` use `https://www.getbifrost.ai/schema`; `tests/e2e/api/**` has Bifrost fixtures; root stray file `1:1-36` is an old commit-message scratch file | defer plus must-change for public examples | Update examples and public fixtures after product docs/config aliases are decided. Leave regression tests alone until source behavior changes. Remove or ignore scratch file separately, not as branding work. |
| BR-045 | Historical changelogs and old releases | Docs/changelogs and module changelogs account for hundreds of matches; `helm-charts/index.yaml` is historical release index | must-retain-for-attribution plus defer | Do not rewrite history. New changelogs should say FrankenGate and may include "formerly/derived from Bifrost" where factual. |
| BR-046 | Internal Go comments, local variable names, package aliases | Raw count includes 551 core files, 165 framework files, 129 transport files, and 115 plugin files | defer | Avoid a broad internal rename before launch. It increases merge conflicts and can perturb low-overhead code paths without improving user-visible brand. |
| BR-047 | Partial FrankenGate code already present | `transports/bifrost-http/main.go:1`, `transports/bifrost-http/main.go:114`, `transports/bifrost-http/main.go:121-140` | must-change follow-through | Existing banner/version output creates an inconsistent mixed identity. Either finish the controlled rebrand or keep it as a fork-only dev banner until release surfaces are aligned. |

## Must-Change Launch Blocklist

These surfaces should block any public FrankenGate release if still pointing at Bifrost/Maxim as owner/brand:

- Public docs identity and domains: `docs/docs.json`, `docs/jsonLd.js`, `docs/googleTag.js`, `docs/supportWidget.js`, active `docs/**/*.mdx`.
- Public UI identity: `ui/index.html`, `ui/app/**`, `ui/components/**`, `ui/public/bifrost-*`, generated embed after rebuild.
- Installers and packages: `npx/bifrost`, `npx/bifrost-cli`, `npx/bifrost-migration-cli`, `ui/package.json`, `cli`.
- Container identity: `transports/Dockerfile*`, `transports/docker-entrypoint.sh`, public examples under `examples/dockers`.
- Chart identity: `helm-charts/bifrost/Chart.yaml`, `helm-charts/bifrost/values.yaml`, `helm-charts/bifrost/values.schema.json`, chart templates, new chart index.
- Config schema: `transports/config.schema.json` `$id`, title, docs, default schema URL.
- Infra packages: `terraform/modules/bifrost`, `terraform/README.md`, `nix/**`, `flake.nix`.
- Release automation if used: `.github/workflows/**`, `.github/workflows/scripts/**`, `Makefile` release targets.
- Public governance/support: `SECURITY.md`, `CODE_OF_CONDUCT.md`, README public sections.

## Compatibility Alias Plan

Initial public release should support both old and new spelling for operational contracts:

- CLI/binaries: new `frankengate` and `frankengate-http`; old `bifrost` and `bifrost-http` wrappers or symlinks emit a deprecation note.
- App dirs: read old `~/.config/bifrost`, `%APPDATA%\\bifrost`, and `~/.bifrost`; write new FrankenGate dirs after migration confirmation.
- Env vars: read `FRANKENGATE_*` first, then `BIFROST_*` aliases. Explicitly document precedence.
- Headers: accept `x-fg-*` only after tests exist; keep `x-bf-*`, `sk-bf-*`, `X-Bifrost-Temp-Token`, and OpenAPI `BifrostError` shapes during compatibility release.
- Helm: introduce `.Values.frankengate` while accepting `.Values.bifrost`; fail only on ambiguous conflicting values with a clear message.
- Terraform/Nix: provide new modules/services while preserving old names through documented state/module migration.
- Go SDK: publish new module path only if old imports remain available or a deliberate major-version break is announced.

## Retention Rules

Keep these uses of Bifrost/Maxim:

- Legal origin: `NOTICE`, `LICENSE`, provenance ledger, and a short attribution section in public docs/README.
- Factual compatibility: "Bifrost-compatible" only where conformance supports it.
- Historical artifacts: old changelogs, old chart index entries, old release notes, and old benchmark citations as historical upstream material.
- Optional Maxim integration: plugin name `maxim`, Maxim SDK import, `x-bf-maxim-*` compatibility headers, docs/assets for the Maxim integration, with clear "external/optional/not endorsed" wording.

Avoid these uses:

- `Maxim HQ`, `Bifrost Team`, `support@getbifrost.ai`, `getmaxim.ai`, or `maximhq/*` as current FrankenGate owner/maintainer/support.
- Upstream logos/badges as FrankenGate product identity.
- "Official Bifrost" or "Maxim" claims except factual origin.
- Public release jobs that write to Maxim registries or depend on Maxim-owned secrets.

## Risks

- A cosmetic global rename would break API clients, config, Helm values, Terraform state, Nix services, scripts, docs, and tests while providing little launch value.
- A partial visible rename is worse than no rename: current runtime banner says FrankenGate while docs, UI, installers, image labels, chart metadata, and schema URLs still say Bifrost/Maxim.
- Reusing Maxim/Bifrost logos, package scopes, or support emails risks trademark/endorsement confusion under Apache-2.0 section 6.
- Keeping old names without a public compatibility statement risks confusing new users and weakening the FrankenGate brand.
- Changing Terraform resource labels or Helm value roots without aliases can force destructive infrastructure migrations.
- Removing `x-bf-*`/`BIFROST_*` too early will break enterprise automation and SDK integrations.

## Recommendations

P0, before any public artifact: choose and reserve FrankenGate GitHub org/repo, npm scope, container registry, Helm repo, docs domain, schema URL, download host, security email, support email, analytics policy, and social links. Effort: 1-2 days plus legal/domain work.

P0, legal: retain `LICENSE`, `NOTICE`, provenance ledger, and non-endorsement language; run trademark/name clearance for FrankenGate. Effort: 0.5 day engineering plus legal review.

P0, release safety: disable or fork all workflows that publish to Maxim/GitHub/Docker/npm/Helm infrastructure before they can run in public. Effort: 0.5-1 day.

P1, public docs/UI/installers: update active docs, UI source, logos, screenshots, package manifests, Docker labels, and install commands; rebuild generated UI bundle. Effort: 3-5 days depending screenshot regeneration.

P1, config/domain: create new schema URL and docs URL, then add alias handling for old schema/env/header names. Effort: 1-3 days with tests.

P2, deployment packaging: publish new Helm/Terraform/Nix identities with compatibility aliases and migration notes. Effort: 3-5 days because Terraform/Nix/Helm state semantics need care.

P2, Go modules: decide whether the first release keeps `github.com/maximhq/bifrost/...` imports as compatibility or publishes new modules. Effort: 2-5 days for module path migration plus CI, more if maintaining dual modules.

P3, Maxim plugin: keep as optional external integration or remove entirely. If kept, rewrite docs around "Maxim" as third-party, not product owner. Effort: 0.5-1 day.

P4, internal symbols: defer broad `Bifrost*` internal type/function renames until after launch and conformance. Effort: large; not justified for launch.

## Alternatives

- Dual-brand compatibility release: public product is FrankenGate, internals/API aliases remain Bifrost-compatible. This is the recommended launch path.
- Hard rename release: rename modules, headers, env vars, binary, chart root, Terraform labels, and DB helper names in one break. Not recommended without a major-version and migration budget.
- Distribution-only fork: keep code/package names Bifrost-compatible and only change README/NOTICE/release origin. Fastest, but weak public brand and higher trademark confusion if visible Bifrost assets remain.
- Remove Maxim integration: eliminates one trademark-bearing third-party surface, but loses an existing observability connector. If removed, delete plugin docs/assets rather than renaming Maxim to FrankenGate.

## Assumptions

- FrankenGate is the intended public name despite earlier roadmap caution about naming risk.
- The first public release should preserve compatibility for current Bifrost automation and clients.
- The Maxim observability plugin remains optional unless explicitly removed later.
- Generated UI bundles are rebuilt from source and not hand-edited.
- Historical changelogs and old chart indexes are archival, not current brand claims.

## Open Questions

1. What are the final public org, repository, npm scope, Docker/OCI namespace, Helm repo, docs domain, schema URL, download host, support email, and security email?
2. What is the minimum compatibility window for `bifrost`, `bifrost-http`, `.bifrost`, `BIFROST_*`, `x-bf-*`, `sk-bf-*`, and Go module paths?
3. Will the public release include the Maxim plugin, or should it be disabled/removed from default docs and builds?
4. Should new API aliases be `x-fg-*`/`sk-fg-*`, or should FrankenGate intentionally keep Bifrost-compatible wire names forever?
5. Is `FrankenGate` legally cleared as a public product mark?

## Final Confidence

High confidence on surface inventory and classification. Medium confidence on exact effort because registry/domain/legal decisions are external to the codebase. Low confidence that a purely mechanical rename is safe; the evidence strongly favors an alias-first rebrand.
