# FrankenGate

**CONTROL SURFACE // BEAUTIFUL MONSTER GATEWAY**

FrankenGate is an AI gateway assembled from proven Bifrost machinery and new
enterprise control parts. The goal is a living gateway kernel for internal AI:
one disciplined membrane between teams, models, tools, budgets, identities, and
evidence.

The current public surface is a compatibility baseline, not the finished
monster. It preserves the low-overhead provider and transport substrate while
the FrankenGate-specific authority systems are built, tested, and promoted
behind explicit evidence gates.

## Current Status

| Area | Status | Local proof |
|---|---|---|
| Fork identity and attribution | Shipped baseline | [NOTICE](NOTICE), [LICENSE](LICENSE), [provenance ledger](docs/roadmap/provenance-ledger.md) |
| Bifrost-compatible Go gateway substrate | Shipped baseline inherited from Bifrost | [release audit](docs/roadmap/release/bif-kyy-14-1-release-audit.md), [stable component baseline](docs/roadmap/release/stable-component-baseline.md) |
| FrankenGate public release workflow | Implemented but still gated | [frankengate-release workflow](.github/workflows/frankengate-release.yml), [release gates](docs/roadmap/release/stable-component-baseline.md#release-gates) |
| Enterprise governance primitives | Implemented but unreleased in isolated slices | [admission](core/admission), [authority epochs](core/authorityepoch), [reservations](core/reservations), [privacy receipts](core/privacy), [MCP ownership](core/mcpownership) |
| Multi-pod virtual keys, Okta access, hard budgets, MCP governance, privacy-safe evals, and extreme availability | Roadmap, not complete | [enterprise program](docs/roadmap/enterprise-oss-program.md), [seam matrix](docs/roadmap/oss-enterprise-seam-matrix.md), [reliability plan](docs/roadmap/extreme-reliability-and-day2-operations.md) |

The detailed marketing claim ledger is maintained in
[docs/roadmap/marketing/claim-ledger.md](docs/roadmap/marketing/claim-ledger.md).
If a claim is not in that ledger with local evidence, it should not appear in
public FrankenGate marketing.

## What FrankenGate Is

FrankenGate is a forked gateway for teams that want the Bifrost provider and
transport foundation, but need stricter enterprise control before launching
inside their own infrastructure. It is being shaped as a control room, not a
demo booth: every serious claim needs a local proof artifact, a status label,
and a release gate.

The product direction is FrankenGate-first. The wire compatibility and much of
the implementation still use Bifrost names because those names are part of the
inherited API, config, and SDK contract. The near-term work is the hard part:
proving that authority can hold across pods without putting optional learning,
eval, or promotion services in the inference availability path.

## What Is Working Now

The repository contains the inherited Bifrost gateway substrate:

- Provider adapters and shared schemas under [core](core).
- HTTP gateway transport under [transports/bifrost-http](transports/bifrost-http).
- Persistence, streaming, tracing, and vector-store framework code under
  [framework](framework).
- Plugins for governance, logging, telemetry, semantic cache, OpenTelemetry,
  mock responses, and compatibility under [plugins](plugins).
- UI, Helm, Terraform, Nix, NPX, and release infrastructure inherited from the
  Bifrost baseline.

The current fork also has local FrankenGate planning and proof artifacts:

- [Branding surface audit](docs/roadmap/frankengate-branding-surface.md)
- [OSS and enterprise seam matrix](docs/roadmap/oss-enterprise-seam-matrix.md)
- [Stable component baseline](docs/roadmap/release/stable-component-baseline.md)
- [Release audit](docs/roadmap/release/bif-kyy-14-1-release-audit.md)
- [Disconnected authorization ADR](docs/roadmap/architecture/disconnected-authorization.md)
- [MCP connection ownership ADR](docs/roadmap/architecture/mcp-connection-ownership.md)
- [Outbox cursor lifecycle design](docs/roadmap/architecture/outbox-cursor-lifecycle.md)
- [Principal deprovisioning design](docs/roadmap/architecture/principal-deprovisioning.md)
- [Privacy and learning boundary](docs/roadmap/privacy-redaction-and-learning-boundaries.md)

## What Is Not Claimed

FrankenGate does not currently claim:

- completed horizontal scaling;
- completed enterprise Kubernetes readiness;
- production-ready Okta or SCIM entitlement enforcement;
- distributed virtual-key revocation across pods;
- Aurora-backed hard budget reservations;
- controlled overdraft and alerting in the request path;
- production MCP governance before credential or connection acquisition;
- privacy-safe trace, replay, eval, or skill-promotion pipelines;
- published FrankenGate npm, Docker, Helm, Terraform, or docs-domain install
  surfaces.

Those are roadmap targets. They need implementation, conformance evidence, and
release gates before they become product claims.

## Compatibility And Naming

FrankenGate is derived from Bifrost and remains Bifrost-compatible where the
code, modules, headers, config keys, binary names, and package paths have not
yet been deliberately migrated. This is intentional for the compatibility
baseline.

Names such as `bifrost-http`, `github.com/maximhq/bifrost/...`, `BIFROST_*`,
`x-bf-*`, `sk-bf-*`, and `BifrostError` are retained as compatibility surfaces
until a tested migration plan exists. They should not be presented as the
current product brand.

The Maxim observability plugin, where present, is an optional inherited
third-party integration. Maxim is not the owner, maintainer, or support route
for FrankenGate.

## Source Verification

This README intentionally does not publish upstream NPX, Docker, Helm, or demo
commands as FrankenGate installation instructions. Current local verification
evidence is recorded in the release documents:

- [Stable component baseline](docs/roadmap/release/stable-component-baseline.md)
- [Release audit](docs/roadmap/release/bif-kyy-14-1-release-audit.md)

For local source verification, use the commands recorded in those documents and
re-run them in a clean checkout before relying on the result. The current
baseline evidence includes local `make build` and selected Go test runs, but it
also records failed or unverified release surfaces. Do not turn that partial
evidence into broad performance, scaling, or release-readiness claims.

## Repository Map

```text
frankengate/
├── core/                         # inherited gateway core plus isolated fork primitives
│   ├── providers/                # provider implementations
│   ├── schemas/                  # shared API and plugin schemas
│   ├── admission/                # unreleased mandatory guard prototype
│   ├── authorityepoch/           # unreleased principal authority epoch prototype
│   ├── mcpownership/             # unreleased MCP ownership prototype
│   ├── privacy/                  # unreleased privacy receipt prototype
│   └── reservations/             # unreleased reservation prototype
├── framework/                    # config, logging, streaming, tracing, vector stores
├── transports/bifrost-http/      # inherited HTTP gateway transport
├── plugins/                      # governance, logging, telemetry, cache, OTEL, etc.
├── ui/                           # inherited web UI source
├── helm-charts/                  # inherited chart surface, not rebranded for release yet
├── terraform/                    # inherited Terraform module surface
├── docs/roadmap/                 # fork planning, proofs, release audits, claim ledgers
└── .github/workflows/            # inherited workflows plus FrankenGate release workflow
```

## Apache-2.0 Attribution

FrankenGate is derived from Bifrost AI Gateway. The upstream work is licensed
under Apache License 2.0, and this fork retains the applicable copyright,
patent, trademark, and attribution notices.

See [LICENSE](LICENSE), [NOTICE](NOTICE), and the
[provenance ledger](docs/roadmap/provenance-ledger.md). FrankenGate is an
independent fork and is not affiliated with or endorsed by Maxim AI or the
Bifrost maintainers.

## Issues And Pull Requests

Issues and pull requests are welcome as evidence, bug reports, or proposed
patches. Merges, releases, and public artifact publication are handled through
protected review paths with human approval.
