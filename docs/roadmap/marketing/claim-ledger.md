# FrankenGate Marketing Claim Ledger

Status: source-of-truth ledger for README and future marketing copy.

Scope: this ledger covers public-facing FrankenGate claims that can be made from
the current repository. It is deliberately conservative. If the evidence is not
local, current, and linked here, the claim should be downgraded or removed.

## Claim Status Vocabulary

| Status | Meaning | Marketing rule |
|---|---|---|
| `shipped baseline` | Present in the fork baseline or inherited Bifrost-compatible substrate, with local evidence. | Can be stated as current capability if wording preserves Bifrost compatibility and attribution. |
| `implemented-but-unreleased` | Code or workflow exists in the current fork, but it is not integrated, released, or proven as an end-to-end product capability. | Can be described as an implementation slice or prototype. Do not present as production feature. |
| `experimental` | Architecture, ADR, prototype, or proof exists, but operational fit is still under evaluation. | Can be used in roadmap or engineering notes. Do not use as buyer-facing feature copy. |
| `roadmap` | Planned target, seam, or known gap. | Can be described as planned work or launch requirement. Do not imply availability. |
| `blocked` | A claim is known to be unsafe until missing proof exists. | Do not publish except as a limitation or release gate. |

## Approved Claim Ledger

| ID | Claim | Status | Local evidence | Approved wording | Forbidden wording |
|---|---|---|---|---|---|
| FG-001 | FrankenGate is derived from Bifrost and preserves Apache-2.0 attribution. | shipped baseline | [NOTICE](../../../NOTICE), [LICENSE](../../../LICENSE), [provenance ledger](../provenance-ledger.md) | "FrankenGate is an Apache-2.0 fork derived from Bifrost." | "Official Bifrost", "Maxim-backed", "Maxim-supported" |
| FG-002 | FrankenGate is independent from Maxim AI and Bifrost maintainers. | shipped baseline | [NOTICE](../../../NOTICE) | "FrankenGate is an independent fork and is not affiliated with or endorsed by Maxim AI or the Bifrost maintainers." | Any wording implying Maxim ownership, support, endorsement, or maintenance. |
| FG-003 | The fork keeps Bifrost-compatible names and wire surfaces during the baseline phase. | shipped baseline | [branding audit](../frankengate-branding-surface.md), [README](../../../README.md) | "Bifrost-compatible baseline" or "compatibility alias." | "Fully rebranded API", "FrankenGate-native SDK surface" |
| FG-004 | A FrankenGate release workflow exists in the repo. | implemented-but-unreleased | [workflow](../../../.github/workflows/frankengate-release.yml), [stable baseline release gates](../release/stable-component-baseline.md#release-gates) | "A FrankenGate GitHub release workflow exists, but release readiness is gated." | "Release pipeline complete", "signed release-ready artifacts" |
| FG-005 | A local clean-archive build produced a FrankenGate-versioned binary in prior audit evidence. | shipped baseline evidence, not a universal release claim | [stable baseline build evidence](../release/stable-component-baseline.md#build-evidence), [release audit](../release/bif-kyy-14-1-release-audit.md) | "Local build evidence exists for audited commits." | "Production binaries are published", "download and install now" |
| FG-006 | Selected non-secret tests passed in release audits. | shipped baseline evidence, partial | [stable baseline test evidence](../release/stable-component-baseline.md#test-evidence), [release audit](../release/bif-kyy-14-1-release-audit.md) | "Selected local tests passed; release gates remain." | "Full test suite green", "release-ready" |
| FG-007 | Framework vector-store integration tests and Docker build were not fully verified in the stable baseline audit. | blocked | [stable baseline test evidence](../release/stable-component-baseline.md#test-evidence), [stable baseline release gates](../release/stable-component-baseline.md#release-gates) | "Release readiness remains blocked by unverified surfaces." | "All integrations verified", "Docker image ready" |
| FG-008 | Provider/transport/plugin substrate exists in inherited source. | shipped baseline | [core](../../../core), [framework](../../../framework), [transports](../../../transports), [plugins](../../../plugins), [seam matrix](../oss-enterprise-seam-matrix.md) | "Inherited Bifrost-compatible gateway substrate." | "FrankenGate-exclusive engine" |
| FG-009 | Mandatory admission guard prototype exists. | implemented-but-unreleased | [core/admission](../../../core/admission), [seam matrix](../oss-enterprise-seam-matrix.md) | "Isolated admission prototype." | "Production reference monitor enforced across the gateway" |
| FG-010 | Authority epoch prototype exists for principal deprovisioning work. | implemented-but-unreleased | [core/authorityepoch](../../../core/authorityepoch), [principal deprovisioning design](../architecture/principal-deprovisioning.md) | "Authority epoch prototype." | "Okta deprovisioning enforced across sessions, keys, caches, and MCP connections" |
| FG-011 | Reservation prototype exists for fenced attempts and accounting lanes. | implemented-but-unreleased | [core/reservations](../../../core/reservations), [seam matrix budget seam](../oss-enterprise-seam-matrix.md) | "In-memory reservation prototype." | "Aurora-backed hard budget reservations complete" |
| FG-012 | Privacy receipt prototype exists. | implemented-but-unreleased | [core/privacy](../../../core/privacy), [privacy boundaries](../privacy-redaction-and-learning-boundaries.md) | "Privacy receipt prototype." | "Production trace/eval/training privacy pipeline complete" |
| FG-013 | MCP connection ownership prototype and ADR exist. | experimental | [core/mcpownership](../../../core/mcpownership), [MCP ownership ADR](../architecture/mcp-connection-ownership.md) | "MCP ownership ADR and prototype." | "Stateful MCP failover complete in Kubernetes" |
| FG-014 | Outbox and disconnected authorization designs exist. | experimental | [outbox cursor lifecycle](../architecture/outbox-cursor-lifecycle.md), [disconnected authorization ADR](../architecture/disconnected-authorization.md) | "Architecture designs for convergence and stale-policy behavior." | "Control-plane convergence implemented" |
| FG-015 | Enterprise seam matrix exists and marks many target capabilities partial, stub, absent, or blocked. | shipped baseline evidence | [seam matrix](../oss-enterprise-seam-matrix.md) | "The seam matrix separates shipped substrate from enterprise gaps." | "Enterprise platform complete" |
| FG-016 | Multi-pod virtual-key lifecycle is a target, not a shipped capability. | roadmap | [enterprise program](../enterprise-oss-program.md), [seam matrix](../oss-enterprise-seam-matrix.md) | "Planned multi-pod virtual-key authority." | "Virtual keys converge across pods today" |
| FG-017 | Hard budgets, top-ups, controlled overdraft, and alerting are not complete. | roadmap | [enterprise program](../enterprise-oss-program.md), [seam matrix](../oss-enterprise-seam-matrix.md), [reservations package](../../../core/reservations) | "Roadmap budget reservation and overdraft controls." | "Hard enterprise budgets complete" |
| FG-018 | Okta/OIDC/SCIM access profile enforcement is not complete. | roadmap | [enterprise program](../enterprise-oss-program.md), [seam matrix](../oss-enterprise-seam-matrix.md), [principal deprovisioning design](../architecture/principal-deprovisioning.md) | "Roadmap identity-derived access." | "Okta entitlements are production-ready" |
| FG-019 | MCP governance before credential/connection acquisition is not complete. | roadmap | [MCP governance roadmap](../mcp-tool-skill-governance-and-research.md), [MCP ownership ADR](../architecture/mcp-connection-ownership.md) | "Roadmap MCP governance membrane." | "MCP governance fully enforced" |
| FG-020 | Privacy-safe traces, replay, evals, and skill-promotion loops are not complete. | roadmap | [privacy boundaries](../privacy-redaction-and-learning-boundaries.md), [promotion contract](../jsm-flywheel-gauntlet-and-promotion-contract.md), [agent evidence envelope](../architecture/agent-evidence-envelope.md) | "Roadmap privacy-safe evidence and human-reviewed promotion loop." | "Autonomous learning platform complete" |
| FG-021 | Horizontal scaling and extreme availability are not claimed complete. | roadmap | [reliability plan](../extreme-reliability-and-day2-operations.md), [seam matrix](../oss-enterprise-seam-matrix.md) | "Extreme availability is a launch requirement under active design." | "Horizontally scalable enterprise gateway" |
| FG-022 | Upstream package/image/chart install commands are not FrankenGate install commands. | blocked | [branding audit BR-006, BR-017, BR-028, BR-030](../frankengate-branding-surface.md) | "No published FrankenGate install command is claimed yet." | `npx @maximhq/bifrost`, `docker run maximhq/bifrost`, upstream Helm commands as FrankenGate installs |
| FG-023 | Upstream benchmark numbers are not current fork marketing proof. | blocked | [stable baseline benchmark methodology](../release/stable-component-baseline.md#repeatable-benchmark-methodology), [release audit unsupported claims](../release/bif-kyy-14-1-release-audit.md) | "Use benchmark numbers only as source-logged regression evidence for audited paths." | "11 microsecond overhead", "5,000 RPS", "perfect success rate" |

## README Claim Checklist

Before editing `README.md`, verify:

- no upstream badge points to `maximhq`, `getbifrost.ai`, `getmaxim.ai`, Docker Hub, Discord, Postman, or Artifact Hub;
- no upstream install command is presented as a FrankenGate install path;
- no benchmark number appears unless this ledger links to current fork evidence for that exact claim;
- every roadmap capability is visibly labeled roadmap, experimental, or implemented-but-unreleased;
- Apache-2.0 attribution and non-endorsement language remain prominent;
- compatibility aliases are described as compatibility, not as current product brand.

## Release Claim Gates

A claim may move from `implemented-but-unreleased` or `roadmap` to `shipped baseline`
only after the ledger is updated with:

1. source path or artifact path;
2. exact test or conformance command;
3. pass/fail result;
4. release tag or commit;
5. known limitations;
6. reviewer/date.

## Search Positioning Notes

SEO copy should target the entity "FrankenGate" first, then describe
"Bifrost-compatible AI gateway fork" as the factual compatibility and origin
phrase. Do not attempt to rank by copying upstream Bifrost pages. The durable
search story is evidence-backed fork governance, not inherited upstream
marketing.
