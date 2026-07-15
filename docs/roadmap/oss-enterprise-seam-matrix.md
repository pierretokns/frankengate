# OSS and Enterprise Seam Matrix

Status: bead `bif-kyy.1.1` deliverable, read-only source audit on 2026-07-15.

Scope: this matrix covers the roadmap capabilities in `docs/roadmap/enterprise-oss-program.md` across schema, migration, store, service, API, authz, UI, Helm/config, telemetry, unit, integration, multi-pod, docs, and packaging. It is a seam map, not an implementation plan. Existing roadmap warnings are treated as confirmed known risks, not new findings.

Legend:

- `present [V]`: implemented in reviewed OSS source with file/line evidence.
- `partial [V]`: usable OSS implementation exists, but it does not satisfy the enterprise launch contract or only covers a narrower layer.
- `stub [V]`: schema, OpenAPI, Helm, UI fallback, or docs advertise the surface, but reviewed OSS runtime implementation is missing.
- `absent [V]`: scoped `rg` searches found no implementation in the reviewed OSS paths.
- `[I]`: inference from source shape or negative search, called out when direct positive evidence is unavailable.

## Roadmap Capability Baseline

The target capabilities are the nine roadmap domains: distributed virtual-key lifecycle, budgets/rates/top-ups, identity/Okta/groups/access profiles, HA/Kubernetes operations, routing/circuit/canary/shadow, traces/replay/evaluation/export, audit/observability/honest dashboard, security posture, and build/release artifacts. The roadmap explicitly requires the same layer classification used here (`docs/roadmap/enterprise-oss-program.md:105-110`) and confirms that OSS already has governance/routing/UI/Helm substrate while some enterprise surfaces are placeholders (`docs/roadmap/enterprise-oss-program.md:113-123`).

## Evidence Index

E01 virtual-key schema: `framework/configstore/tables/virtualkey.go:13-23`, `framework/configstore/tables/virtualkey.go:25-45`, `framework/configstore/tables/virtualkey.go:169-185`, `framework/configstore/tables/virtualkey.go:217-255`.

E02 budget/rate/team/customer schema: `framework/configstore/tables/budget.go:10-47`, `framework/configstore/tables/budget.go:49-83`, `framework/configstore/tables/ratelimit.go:10-45`, `framework/configstore/tables/team.go:11-48`, `framework/configstore/tables/customer.go:9-35`.

E03 routing schema: `framework/configstore/tables/routingrules.go:12-46`, `framework/configstore/tables/routingrules.go:97-111`.

E04 identity/OAuth/SCIM schema seams: `framework/configstore/tables/clientconfig.go:27`, `framework/configstore/tables/clientconfig.go:52-60`, `framework/configstore/tables/mcpoauth2server.go:10-42`, `framework/configstore/tables/mcpoauth2issuance.go:10-27`, `framework/configstore/tables/mcpoauth2issuance.go:61-129`.

E05 log and node-usage schema: `framework/logstore/tables.go:125-217`, `framework/logstore/tables.go:944-979`, `framework/logstore/tables.go:1796-1817`.

E06 config migrations: `framework/configstore/migrations.go:314-336`, `framework/configstore/migrations.go:349-375`, `framework/configstore/migrations.go:401-424`, `framework/configstore/migrations.go:431-444`, `framework/configstore/migrations.go:10389-10480`.

E07 config store interface: `framework/configstore/store.go:17-30`, `framework/configstore/store.go:58-63`, `framework/configstore/store.go:114-161`, `framework/configstore/store.go:288-358`, `framework/configstore/store.go:438-459`, `framework/configstore/store.go:477-615`, `framework/configstore/store.go:707-756`.

E08 relational store implementation seams: `framework/configstore/rdb.go:91-118`, `framework/configstore/rdb.go:825-907`, `framework/configstore/rdb.go:6848-7007`, `framework/configstore/rdb.go:7015-7368`.

E09 governance plugin init: `plugins/governance/main.go:134-242`, `plugins/governance/main.go:245-330`.

E10 governance service hooks: `plugins/governance/main.go:408-576`, `plugins/governance/main.go:677-747`, `plugins/governance/main.go:924-1108`, `plugins/governance/main.go:1192-1310`, `plugins/governance/main.go:1322-1389`, `plugins/governance/main.go:1400-1478`, `plugins/governance/main.go:1570-1610`.

E11 governance local store: `plugins/governance/store.go:24-63`, `plugins/governance/store.go:68-90`, `plugins/governance/store.go:100-213`, `plugins/governance/store.go:215-248`, `plugins/governance/store.go:523-620`, `plugins/governance/store.go:625-976`.

E12 usage accounting: `plugins/governance/tracker.go:15-63`, `plugins/governance/tracker.go:91-171`, `plugins/governance/tracker.go:173-260`.

E13 routing engine: `plugins/governance/routing.go:17-55`, `plugins/governance/routing.go:79-150`, `plugins/governance/routing.go:168-260`.

E14 governance management API: `transports/bifrost-http/handlers/governance.go:46-165`, `transports/bifrost-http/handlers/governance.go:167-321`, `transports/bifrost-http/handlers/governance.go:988-1047`, `transports/bifrost-http/handlers/governance.go:2914-2996`, `transports/bifrost-http/handlers/governance.go:3003-3482`, `transports/bifrost-http/handlers/governance.go:3549-3848`, `transports/bifrost-http/handlers/governance.go:4661-4833`.

E15 logs API: `transports/bifrost-http/handlers/logging.go:266-302`, `transports/bifrost-http/handlers/logging.go:433-472`, `transports/bifrost-http/handlers/logging.go:683-725`.

E16 health/readiness API: `transports/bifrost-http/handlers/health.go:28-31`, `transports/bifrost-http/handlers/health.go:45`, `transports/bifrost-http/handlers/health.go:97`.

E17 MCP auth/OAuth APIs: `transports/bifrost-http/handlers/mcpserver.go:38-78`, `transports/bifrost-http/handlers/mcpserver.go:134-138`, `transports/bifrost-http/handlers/mcpserver.go:623-746`, `transports/bifrost-http/handlers/mcpoauth2.go:36-37`, `transports/bifrost-http/handlers/mcpoauth2consent.go:78-79`, `transports/bifrost-http/handlers/mcpoauth2discovery.go:37-39`, `transports/bifrost-http/handlers/mcpoauth2issuance.go:53-54`, `transports/bifrost-http/handlers/mcpoauth2sessions.go:26-27`.

E18 OpenAPI stubs and security schemes: `docs/openapi/openapi.yaml:813-871`, `docs/openapi/openapi.yaml:873-919`, `docs/openapi/openapi.yaml:921-945`, `docs/openapi/openapi.yaml:947-955`, `docs/openapi/openapi.yaml:1095-1115`.

E19 OSS UI working surfaces: `ui/app/workspace/virtual-keys/views/virtualKeySheet.tsx:247-248`, `ui/app/workspace/virtual-keys/views/virtualKeysTable.tsx:340-342`, `ui/app/workspace/governance/views/teamSheet.tsx:102-103`, `ui/app/workspace/governance/views/teamsTable.tsx:172-174`, `ui/app/workspace/governance/views/customerSheet.tsx:73-74`, `ui/app/workspace/governance/views/customerTable.tsx:148-150`, `ui/app/workspace/routing-rules/views/routingRuleSheet.tsx:92-93`, `ui/app/workspace/logs/page.tsx:38-39`, `ui/app/workspace/dashboard/components/exportPopover.tsx:17`, `ui/app/workspace/observability/views/observabilityView.tsx:86`.

E20 UI RBAC and enterprise fallbacks: `ui/app/_fallbacks/enterprise/lib/contexts/rbacContext.tsx:59-78`, `ui/app/_fallbacks/enterprise/components/views/contactUsView.tsx:15-43`, `ui/app/_fallbacks/enterprise/components/cluster/clusterView.tsx:4-15`, `ui/app/_fallbacks/enterprise/components/circuit-breaker/circuitBreakerView.tsx:4-15`, `ui/app/_fallbacks/enterprise/components/audit-logs/auditLogsView.tsx:4-15`, `ui/app/_fallbacks/enterprise/components/access-profiles/accessProfilesIndexView.tsx:4-16`, `ui/app/workspace/governance/layout.tsx:7-26`, `ui/app/workspace/cluster/layout.tsx:7-14`, `ui/app/workspace/audit-logs/layout.tsx:7-14`, `ui/app/workspace/circuit-breaker/layout.tsx:7-15`.

E21 Helm/Kubernetes runtime chart: `helm-charts/bifrost/values.yaml:37-44`, `helm-charts/bifrost/values.yaml:133-164`, `helm-charts/bifrost/values.yaml:241-323`, `helm-charts/bifrost/values.yaml:867-905`, `helm-charts/bifrost/templates/deployment.yaml:1-8`, `helm-charts/bifrost/templates/deployment.yaml:23-88`, `helm-charts/bifrost/templates/deployment.yaml:220-275`, `helm-charts/bifrost/templates/hpa.yaml:1-38`, `helm-charts/bifrost/templates/service-headless.yaml:1-35`, `helm-charts/bifrost/templates/rbac.yaml:1-38`.

E22 Helm/config schema enterprise surfaces: `transports/config.schema.json:4946-4965`, `transports/config.schema.json:5137-5157`, `transports/config.schema.json:5771-5792`, `transports/config.schema.json:6350-6375`, `helm-charts/bifrost/values.schema.json:2061-2162`, `helm-charts/bifrost/values.schema.json:2241-2305`, `helm-charts/bifrost/values.schema.json:2844-2910`, `helm-charts/bifrost/values.schema.json:3438-3490`, `helm-charts/bifrost/values.schema.json:3513-3562`, `helm-charts/bifrost/values.schema.json:3672-3758`.

E23 telemetry/logging/tracing: `plugins/logging/main.go:302-303`, `plugins/logging/main.go:399`, `plugins/logging/main.go:479-484`, `plugins/logging/main.go:599-635`, `plugins/logging/main.go:861-886`, `plugins/logging/main.go:942`, `plugins/logging/main.go:1020-1028`, `plugins/logging/main.go:1065-1072`, `plugins/logging/main.go:1331-1377`, `plugins/telemetry/main.go:37`, `plugins/telemetry/main.go:255`, `plugins/telemetry/main.go:631`, `plugins/otel/main.go:31-96`, `framework/tracing/tracer.go:43`, `framework/tracing/tracer.go:81-144`, `framework/tracing/helpers.go:10-77`.

E24 test surfaces: `plugins/governance/tracker_test.go`, `plugins/governance/routing_test.go`, `plugins/governance/store_test.go`, `framework/configstore/dlock_test.go`, `framework/configstore/rdb_oauth2_test.go`, `framework/configstore/scopeddb_test.go`, `transports/bifrost-http/handlers/governance_test.go`, `transports/bifrost-http/handlers/mcpserver_auth_test.go`, `transports/bifrost-http/handlers/mcpoauth2issuance_test.go`, `transports/bifrost-http/handlers/mcpoauth2jwt_test.go`, `plugins/logging/redaction_test.go`, `plugins/telemetry/main_test.go`, `plugins/otel/converter_test.go`, `transports/schema_test/config_schema_test.go`, `tests/governance/e2e_test.go`, `tests/governance/vkbudget_test.go`, `tests/governance/inmemorysync_test.go`, `tests/e2e/features/virtual-keys/virtual-keys.spec.ts`, `tests/e2e/features/governance/governance.spec.ts`, `tests/e2e/features/routing-rules/routing-rules.spec.ts`, `tests/e2e/features/logs/logs.spec.ts`, `tests/e2e/features/dashboard/dashboard.spec.ts`, `tests/e2e/features/observability/observability.spec.ts`, `tests/e2e/features/placeholders/placeholders.spec.ts`.

E25 docs: `docs/features/governance/virtual-keys.mdx`, `docs/features/governance/budget-and-limits.mdx`, `docs/features/governance/routing.mdx`, `docs/providers/provider-routing.mdx:1236-1245`, `docs/providers/provider-routing.mdx:1405-1448`, `docs/providers/provider-routing.mdx:1473-1531`, `docs/providers/provider-routing.mdx:1594-1595`, `docs/enterprise/setting-up-okta/oidc.mdx`, `docs/enterprise/setting-up-okta/scim.mdx`, `docs/enterprise/rbac.mdx`, `docs/enterprise/access-profiles.mdx`, `docs/enterprise/audit-logs.mdx`, `docs/enterprise/clustering.mdx`, `docs/enterprise/log-exports.mdx:265`, `docs/deployment-guides/helm/storage.mdx:563`.

E26 packaging/release: `transports/Dockerfile:2-20`, `transports/Dockerfile:53-62`, `transports/Dockerfile.redhat:61`, `helm-charts/bifrost/Chart.yaml:3`, `npx/bifrost/package.json:2-18`, `npx/bifrost-cli/package.json:2-19`, `terraform/modules/bifrost/kubernetes/main.tf:5-12`, `terraform/modules/bifrost/kubernetes/main.tf:18-29`, `terraform/modules/bifrost/kubernetes/main.tf:46-69`, `terraform/modules/bifrost/kubernetes/main.tf:209-239`, `Makefile:322`, `Makefile:489-502`, `Makefile:792`, `Makefile:923`, `Makefile:1574-1589`, `docs/security.mdx:48`, `docs/security.mdx:139`, `docs/security.mdx:214`, `docs/security.mdx:254`, `docs/security.mdx:286`, `docs/release-cadence.mdx:7-39`.

Negative evidence:

- N01 multi-pod acceptance tests: `rg -n --glob '!docs/openapi/**' --glob '!ui/out/**' "three pods|3 pods|multi-pod|multipod|multi pod|kind|k3d|chaos|partition|failover.*pod|shared budget|governance_startup_reset|NodeUsage|cluster" tests framework plugins transports/bifrost-http docs/roadmap docs/deployment-guides helm-charts` found roadmap/chart/logging/dlock/node-usage surfaces, but no three-pod create/use/revoke/rotate or shared-budget acceptance test outside roadmap text.
- N02 runtime enterprise handlers: `rg -n --glob '!docs/openapi/**' --glob '!ui/out/**' "AccessProfileHandler|access-profiles|TableAccessProfile|AuditLogsHandler|audit-logs|TableAudit|CircuitBreakerHandler|circuit-breaker|TableCircuit|SCIMHandler|scim|Canary|Shadow|Replay|EvaluationJob|TopUp|Overdraft|Reservation|rotation_family|policy_version|not_before" transports/bifrost-http/handlers plugins framework ui/app tests docs/roadmap helm-charts` found Helm/config/OpenAPI/UI fallback/docs references and stream gate replay internals, but no OSS runtime handler/store/service for access profiles, audit logs, circuit breaker, SCIM users/groups, top-up, overdraft, budget reservation, route canary/shadow, or replay/eval jobs.

## Matrix

### 1. Distributed Virtual-Key Lifecycle

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | partial [V: E01] | VK rows have stable IDs, secret value field, active flag, expiry, team/customer ownership, provider/MCP configs, budgets, rate limits, and config hash. Roadmap-required `not_before`, lifecycle states, rotation family, policy version, and last-used metadata are not present as first-class columns. |
| Migration | partial [V: E06] | Existing migrations cover governance tables/config hash/created-by/access-profile ID seams, but no versioned invalidation or lifecycle-state migration is visible. |
| Store | partial [V: E07, E08, E11] | ConfigStore and LocalGovernanceStore support VK CRUD/cache/indexing, but the hot cache is process-local and lacks a proven post-commit invalidation cursor. |
| Service | partial [V: E09, E10] | Governance hooks validate VKs, evaluate provider/model/MCP limits, and apply routing before requests. Enterprise launch needs versioned, cross-pod create/revoke/rotate convergence and fail-closed stale-cache behavior. |
| API | partial [V: E14, E18] | Management API covers create/list/detail/update/delete/rotate/bulk rotate/quota. It does not expose idempotency keys, resource version returns, explicit revoke state, rotation overlap policy, or top-up receipt semantics. |
| Authz | partial [V: E10, E17, E20] | Inference/MCP authorization exists, and management API has session/basic middleware, but OSS UI RBAC allows all and enterprise resource-level server RBAC is not present in reviewed source. |
| UI | present [V: E19] | VK create/edit/delete/rotate tables and sheets exist. Enterprise seam is hiding or disabling lifecycle actions whose backend semantics are absent. |
| Helm/config | partial [V: E21, E22] | Chart can enforce inference auth, secrets, probes, and cluster config. No value controls revocation freshness SLO, invalidation backend, or fail-closed cache lease. |
| Telemetry | partial [V: E05, E23] | Logs include virtual-key IDs and selected key metadata. Missing: policy version, invalidation lag, stale-cache failures, and reveal-once/rotation audit evidence. |
| Unit | present [V: E24] | Governance store/accounting/VK handler tests exist. They do not prove distributed lifecycle semantics. |
| Integration | partial [V: E24] | Governance and VK E2E/API tests exist. They are not the roadmap's three-pod create/use/revoke/rotate acceptance test. |
| Multi-pod | absent [V: N01] | Cluster/logging/dlock surfaces exist, but no reviewed test proves a newly created key works across three pods or that revocation/rotation converges in 1-5s. |
| Docs | present [V: E25] | OSS governance docs exist; enterprise lifecycle docs must stop short of claims until convergence evidence exists. |
| Packaging | present [V: E26] | Docker/Helm/NPM/Terraform surfaces exist; launch packaging must add migration/invalidation toggles once designed. |

### 2. Budgets, Rates, Top-Ups, Controlled Overdraft

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | partial [V: E02, E22] | Budgets/rate limits cover max/current usage, reset windows, owners, and alert-rule schema. There is no budget reservation ledger, overdraft grant, approval receipt, or top-up table. |
| Migration | partial [V: E06] | Migrations add multi-budget/rate-limit ownership and customer budgets, but not reservations, top-ups, overdrafts, or settlement rows. |
| Store | partial [V: E07, E08, E11] | Store has CRUD and owner locks; LocalGovernanceStore maintains in-memory counters. Hard shared limits need an Aurora authority path with idempotent reservation/settlement. |
| Service | partial [V: E10, E12] | UsageTracker dedupes updates and records multi-scope usage after calls. It is not a pre-provider atomic quota reservation and has no controlled overdraft approval path. |
| API | partial [V: E14] | Budgets/rate limits are exposed through governance APIs and owner resources. There is no top-up, overdraft, reservation, renewal, refund, or alert-transition API. |
| Authz | partial [V: E20] | UI action gates exist but OSS fallback allows all. Enterprise top-up/overdraft requires reviewer-not-author and scope-aware server authorization. |
| UI | partial [V: E19, E20] | Budgets/rates appear in governance surfaces; alerting has schema/fallback surfaces. No audited top-up/overdraft/reservation dashboard is present. |
| Helm/config | stub [V: E22] | Helm schema has alert rules against governance metrics, but no counter authority backend or overdraft policy knobs. |
| Telemetry | partial [V: E05, E23] | Log records include governance IDs and costs; missing reservation ID, denial receipt, overshoot bound, and alert transition evidence. |
| Unit | partial [V: E24] | Accounting, reset, and governance tests exist; no durable reservation/overdraft race test is visible. |
| Integration | partial [V: E24] | Governance/rate-limit/VK-budget E2E surfaces exist; they do not prove simultaneous multi-pod hard-budget behavior. |
| Multi-pod | absent [V: N01] | No acceptance test proves concurrent requests cannot exceed a shared hard budget beyond a documented reservation bound. |
| Docs | partial [V: E25] | Budget/rate docs exist; controlled overdraft/top-up contract remains roadmap-level. |
| Packaging | present [V: E26] | Base artifacts exist; no packaging seam for an authority worker/lease process is present. |

### 3. Identity, Okta, Groups, and Access Profiles

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | stub [V: E04, E18, E22] | SCIM/OAuth config and access-profile OpenAPI/Helm surfaces exist. Reviewed OSS lacks first-class SCIM Users/Groups, access-profile, role-mapping, group-membership, and entitlement-version tables. |
| Migration | partial [V: E06] | Migrations include SCIM auth flag, OAuth2 issuance/server tables, and access-profile ID seams. They do not create standards-complete directory/access-profile schemas. |
| Store | partial [V: E07, E08, E11] | Store supports MCP per-user OAuth/header credentials, sessions, and enterprise-only user governance interfaces. Directory sync, access-profile propagation, and explain-access stores are absent from reviewed OSS. |
| Service | partial [V: E10, E12, E17] | MCP OAuth and user ID hooks exist; governance has enterprise-only user structs. OIDC login, inbound SCIM Users/Groups, Okta import checkpoints, and group-to-profile reconciliation are not implemented in reviewed OSS runtime. |
| API | stub [V: E17, E18, N02] | OAuth/MCP APIs exist. OpenAPI advertises RBAC/access-profile routes, and middleware whitelists SCIM OAuth callback routes, but scoped search found no OSS access-profile/SCIM user-group handlers. |
| Authz | partial [V: E20] | Workspace routes call RBAC hooks, but OSS fallback returns true for all permissions. Enterprise needs server-side resource/operation checks on every management mutation. |
| UI | stub [V: E20] | SCIM/RBAC/access-profile pages are fallback upsell components, while governance shell gates reference the resources. |
| Helm/config | stub [V: E21, E22] | Helm values and schema validate Okta/SCIM configuration and render config fields; this is not evidence of runtime sync or entitlement enforcement. |
| Telemetry | partial [V: E05, E23] | Logs have user/team/customer/business-unit fields. Missing mapping-version, sync checkpoint, profile derivation, and explain-access telemetry. |
| Unit | partial [V: E24] | OAuth/MCP auth tests exist. No SCIM Users/Groups parser, Okta reconciler, access-profile propagation, or RBAC boundary unit tests were found. |
| Integration | partial [V: E24] | Auth matrix and MCP auth API collections exist; no Okta/SCIM end-to-end removal-to-entitlement-revocation evidence. |
| Multi-pod | absent [V: N01, N02] | No reviewed test proves group removal removes model visibility/invocation rights consistently across pods. |
| Docs | present [V: E25] | Public enterprise docs cover Okta/SCIM/RBAC/access profiles as requirements inputs. |
| Packaging | partial [V: E21, E26] | Chart can pass SCIM/Okta config and secrets; enterprise image/module boundary is not present in reviewed OSS. |

### 4. High Availability and Kubernetes Operations

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | partial [V: E05, E22] | Config schemas include cluster config and log node-usage cursors. They do not define cache freshness leases, migration fences, or subsystem fail-open/closed policies. |
| Migration | partial [V: E06] | Distributed lock and async job migrations exist; mixed-version migration windows and fencing-token scheduler tables are not evident. |
| Store | partial [V: E07, E08] | Distributed lock store methods and owner locks exist. Durable counter authority and invalidation outbox stores remain seams. |
| Service | partial [V: E09, E16, E23] | Startup reset lock, readiness/liveness routes, and cluster node log attribution exist. Drain semantics, cache freshness, and counter-authority readiness are not proven. |
| API | partial [V: E16] | Health/readiness APIs exist. Cluster admin API is not present in reviewed OSS; cluster UI is a fallback page. |
| Authz | stub [V: E20] | Cluster route has a UI RBAC gate, but OSS fallback allows all and there is no reviewed server cluster-admin authorization surface. |
| UI | stub [V: E20] | Cluster page is an enterprise contact-us fallback. |
| Helm/config | present [V: E21, E22] | Helm provides service account/RBAC for pod discovery, probes, HPA, cluster gossip/gRPC ports, headless service, secret refs, node scheduling hooks, and validation. |
| Telemetry | partial [V: E05, E23] | Logs attach cluster node ID and node-usage recovery fields. Missing cache lag, invalidation age, lease owner, migration fence, and failover SLO metrics. |
| Unit | partial [V: E24] | Distributed lock, health, schema, and scoped DB tests exist. |
| Integration | partial [V: E24] | Governance sync tests exist, but not Kubernetes rolling-upgrade or pod-death tests. |
| Multi-pod | absent [V: N01] | No three-pod, partition, counter-loss, database-failover, or rolling-upgrade acceptance suite was found. |
| Docs | present [V: E25] | Clustering and Helm docs exist, but should be treated as deployment guidance until launch acceptance evidence is added. |
| Packaging | present [V: E21, E26] | Helm, Docker, Terraform, and values examples provide deployment substrate. |

### 5. Routing, Circuit Breaking, Canaries, and Shadow Traffic

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | partial [V: E03, E22] | Routing rules/targets exist. Circuit breaker schema exists as config/Helm surface; canary/shadow policy schemas are not present. |
| Migration | partial [V: E06] | Routing rules/targets migrate. No circuit state, canary cohort, shadow job, or promotion-history migration is visible. |
| Store | partial [V: E07, E11] | Routing-rule CRUD and in-memory rule snapshots exist. There is no reviewed store for circuit state, deterministic rollout assignment, shadow receipts, or promotion decisions. |
| Service | partial [V: E10, E13] | CEL rule matching, scope precedence, chain depth, weighted target selection, and governance pruning exist. Health/circuit filtering, deterministic canaries, separate shadow budgets, and rollback gates are absent. |
| API | partial [V: E14, E18, N02] | Routing-rule APIs exist. OpenAPI advertises circuit breaker APIs, but scoped search found no OSS runtime circuit handler. |
| Authz | partial [V: E20] | Routing UI gates exist; OSS fallback permits all, and no server-side routing-rule RBAC was verified. |
| UI | partial [V: E19, E20] | Routing rules UI/tree is real. Circuit breaker and adaptive routing are fallback placeholders. |
| Helm/config | stub [V: E22] | Circuit breaker config schema exists; no runtime binding was verified. |
| Telemetry | partial [V: E05, E23] | Routing rule ID/name are logged. Missing circuit state transitions, canary cohort IDs, shadow run IDs, and promotion gate telemetry. |
| Unit | partial [V: E24] | Routing tests exist; no circuit/canary/shadow determinism tests were found. |
| Integration | partial [V: E24] | Routing API/E2E collections exist; no circuit/canary/shadow acceptance flow. |
| Multi-pod | absent [V: N01, N02] | No multi-pod deterministic rollout, rollback, or shadow-budget test was found. |
| Docs | partial [V: E25] | Routing docs are detailed; circuit/canary/shadow remain roadmap/enterprise-doc inputs. |
| Packaging | present [V: E26] | Base artifacts exist; no separate router/circuit artifact seam. |

### 6. Traces, Replay, Evaluation, and Environment Export

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | partial [V: E05, E22] | Log/MCP log schemas capture rich request metadata and redaction fields; audit/log export config exists. Immutable trace envelopes, replay jobs, eval results, evaluator versions, and environment exports are absent. |
| Migration | partial [V: E06] | Log tables/materialized views and async job migrations exist, but no replay/eval/export-specific tables were found. |
| Store | partial [V: E05, E07] | Logstore and async-job methods exist; no dedicated trace snapshot, replay store, evaluation store, or privacy receipt store is visible. |
| Service | partial [V: E23] | Logging, OpenTelemetry, tracing helper, and stream accumulation paths exist. Replay/eval/export workers are absent from reviewed OSS runtime. |
| API | partial [V: E15] | Logs, histograms, dashboard, and MCP logs APIs exist. No replay/eval/export management API was verified. |
| Authz | partial [V: E20] | Logs reveal/delete UI gates exist; OSS fallback permits all and server-side privacy-scoped trace access was not verified. |
| UI | partial [V: E19] | Logs, MCP logs, dashboard export, and observability UI exist. No replay/eval workbench or environment export UI was found. |
| Helm/config | partial [V: E21, E22] | Observability/log export knobs exist; no replay/eval worker isolation or sandbox network policy knobs. |
| Telemetry | present [V: E23] | Logging/Prometheus/OTEL/tracing plugins exist with redaction/filtering hooks. |
| Unit | partial [V: E24] | Logging redaction, telemetry, OTEL converter tests exist. Replay/eval privacy and side-effect tests are absent. |
| Integration | partial [V: E24] | Logs/dashboard/observability E2E tests exist. No replay dry-run/shadow acceptance flow. |
| Multi-pod | absent [V: N01, N02] | No replay scheduler lease/fencing, partition, or pod death test was found. |
| Docs | partial [V: E25] | Observability/log-export docs exist; replay/eval/export remains roadmap-level. |
| Packaging | present [V: E26] | Base artifacts exist; no dedicated evaluator/replay artifact. |

### 7. Audit, Observability, and Honest Dashboard

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | partial/stub [V: E05, E18, E22] | Logs and MCP logs are real; audit-log OpenAPI/config/Helm surfaces are stubs without reviewed audit event table/service. |
| Migration | partial [V: E06] | Logstore migrations and async jobs exist. No tamper-evident audit chain/signed batch migration was found. |
| Store | partial [V: E05, E07] | Logstore supports request/MCP logs and node-usage cursors. Append-only audit store, retention/legal hold, and verification state are absent. |
| Service | partial [V: E23] | Logging, metrics, OTEL, cost recalculation, and trace injection exist. Audit integrity and honest capability manifest are not implemented in reviewed OSS. |
| API | partial/stub [V: E15, E18, N02] | Logs APIs are real; audit-log APIs are OpenAPI references with no reviewed OSS handler. |
| Authz | partial [V: E20] | Logs/audit pages use RBAC hooks, but OSS fallback allows all. |
| UI | partial/stub [V: E19, E20] | Dashboard/logs/observability are real; audit page is an enterprise contact-us fallback. |
| Helm/config | partial/stub [V: E21, E22] | Audit log HMAC/object-storage config exists in schema/values; runtime sink was not verified. |
| Telemetry | present [V: E23] | Metrics/logging/tracing plugins exist. Missing evidence that dashboard hides unsupported enterprise pages via a server capability manifest. |
| Unit | partial [V: E24] | Logging/telemetry tests exist; no audit-chain verification tests were found. |
| Integration | partial [V: E24] | Logs/dashboard/observability E2E tests exist; placeholders are explicitly tested as loadable. |
| Multi-pod | partial [V: E05, N01] | Node usage recovery schema exists, but no cluster audit/log consistency acceptance suite was found. |
| Docs | present [V: E25] | Audit/observability/log-export docs exist as requirements and user guidance. |
| Packaging | present [V: E26] | Base packaging exists; audit archival credentials need runtime implementation before launch claims. |

### 8. Security Posture

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | partial [V: E01, E04, E05, E22] | Secret/config/redaction/OAuth fields exist. Missing tenant-scoped access-profile schema, audit integrity schema, and privacy receipts. |
| Migration | partial [V: E06] | Migrations cover auth, required/logging headers, OAuth, temp tokens, and whitelisted routes. Tenant isolation and audit-chain migrations are absent. |
| Store | partial [V: E07, E08] | ScopedDB, OAuth sessions, locks, and governance stores exist. Every store query is not yet proven tenant-scoped. |
| Service | partial [V: E10, E17, E23] | Governance fail-closed paths, MCP OAuth/auth, redaction, and tracing controls exist. SCIM parser hardening, CSRF/session controls for all enterprise APIs, and privacy-safe replay are not verified. |
| API | partial [V: E14, E15, E17, E18] | Management, logs, governance, and OAuth APIs exist; OpenAPI has auth schemes. Enterprise-only APIs must not be exposed unless backed by authorization and audit. |
| Authz | partial [V: E20] | OSS fallback RBAC allows all; route-level UI gates are not a security boundary. |
| UI | partial [V: E19, E20] | Security/config views and RBAC gates exist; enterprise placeholders must be capability-hidden for honest launch posture. |
| Helm/config | partial [V: E21, E22] | Auth enforcement, secret refs, encryption key secrets, probes, and pod security controls exist. Network policies and key rotation controls remain seams. |
| Telemetry | partial [V: E05, E23] | Redaction/content logging controls and log metadata exist; raw payload safety depends on config and needs stronger launch defaults/evidence. |
| Unit | partial [V: E24] | Redaction, OAuth, schema, governance, and auth tests exist. Fuzzing for SCIM/policy/authorization boundaries is absent. |
| Integration | partial [V: E24] | Auth matrix and MCP auth flows exist; no full tenant-escape/confused-deputy acceptance suite. |
| Multi-pod | absent [V: N01] | No partition/stale-authorization/counter-bypass chaos suite was found. |
| Docs | present [V: E25, E26] | Security hardening/release guidance exists; provenance/SBOM/signing must be verified by artifact gate. |
| Packaging | partial [V: E26] | Docker/Helm/NPM/Terraform exist and security docs mention scanning/provenance, but clean-checkout SBOM/signature/checksum evidence is not part of this bead. |

### 9. Build and Release Artifacts

| Layer | OSS status | Enterprise seam |
|---|---|---|
| Schema | partial [V: E22] | Config and chart schemas are versioned artifacts. Release provenance/SBOM/checksum schema is not a runtime schema. |
| Migration | absent [V: N02] | No release-artifact migration is expected; runtime migrations must be included in future release gates. |
| Store | absent [V: N02] | No artifact ledger/store is present in reviewed OSS. Future provenance ledger can live under roadmap/release tooling, not inference hot path. |
| Service | partial [V: E26] | Makefile build/test/package targets exist. Clean-checkout multi-arch, signed, reproducible release service is not verified here. |
| API | absent [V: N02] | No release artifact API is expected for launch gateway runtime. |
| Authz | absent [V: N02] | Release publishing authorization lives in protected Git/CI, not OSS runtime. |
| UI | absent [V: N02] | No release-management UI is needed for gateway launch. |
| Helm/config | present [V: E21, E22, E26] | Helm chart, chart schema, and index target exist. |
| Telemetry | absent [V: N02] | No artifact-build telemetry surface was found in runtime. |
| Unit | partial [V: E24, E26] | Unit/test targets and suites exist; this bead did not run the full gate. |
| Integration | partial [V: E24, E26] | Integration/E2E runners exist. Clean-checkout artifact verification remains for `bif-kyy.1.2`/release-gate work. |
| Multi-pod | partial [V: E21] | Chart supports replicas/HPA/cluster ports, but there is no release acceptance proof for rolling upgrades across pods. |
| Docs | present [V: E25, E26] | Release cadence, security, Helm, and deployment docs exist. |
| Packaging | present [V: E26] | Dockerfiles, Helm chart, NPM packages, Terraform module, and Make targets are present. Missing verified SBOM/signature/checksum/provenance evidence for launch. |

## Critical Seams and Blast Radius

1. Virtual-key convergence is the first dependency seam. VK schemas, APIs, UI, and auth hooks are real, but a cross-pod invalidation/lease authority is not. Downstream Okta entitlements, access profiles, MCP auth, and routing all depend on the same freshness contract.

2. Hard budgets cannot be derived from the current post-call tracker. The existing governance accounting is valuable telemetry and soft-limit substrate, but enterprise launch needs pre-provider reservation, renewal, settlement, refund, and controlled overdraft receipts before multi-pod hard budget claims.

3. Enterprise identity surfaces are mostly seams, not runtime. SCIM/Okta/access-profile/RBAC pages and schemas exist, but OSS fallback RBAC allows all and runtime handlers/stores for access profiles and SCIM Users/Groups were not found. Treat those as clean-room implementation contracts.

4. Routing must preserve governance ordering. Existing routing rules run with governance hooks and log rule IDs, but circuit/canary/shadow additions must not reintroduce candidates removed by entitlement or bypass quota reservation.

5. Audit and replay are separate from logs/traces. Logs, OTEL, and dashboards are real; tamper-evident audit, immutable replay envelopes, evaluator jobs, and privacy receipts are separate missing subsystems and should stay outside the inference availability path.

6. Helm is ahead of runtime in several enterprise areas. Cluster, SCIM, audit, alerting, and circuit config entries exist. Presence in chart/schema must not be treated as implementation proof.

7. Multi-pod proof is the largest test gap. The chart has replicas/HPA/cluster ports and code has locks/log node metadata, but the roadmap acceptance tests for three pods, partitions, rolling upgrades, and shared budgets are absent from reviewed tests.

## Dependency Implications

- `bif-kyy.6.4` should depend on the distributed VK/config freshness seam, not on Redis or gossip as an authority.
- `bif-kyy.4.4` should treat current budgets/rates as partial OSS substrate and design a separate Aurora reservation authority.
- `bif-kyy.2.1` should introduce first-class tenant/principal/group/access-profile/version/audit schemas rather than overloading existing team/customer/VK tables.
- Routing/circuit/canary/shadow work should depend on entitlement and reservation contracts, because those stages must run before candidate expansion and rollout selection.
- Replay/eval/export work should depend on privacy-safe trace envelopes and a side-effect policy, not directly on the current log table.

## Assumptions and Uncertainty

- This audit covers the local OSS checkout and docs/roadmap context only. It does not inspect unavailable Maxim enterprise source or images.
- Negative evidence is scoped to the paths and patterns listed in N01/N02; naming changes could hide implementations, but OpenAPI/UI/Helm references make the expected names and domains explicit enough for high confidence.
- Some store and service functions are broad; line ranges identify entry points and seams rather than every call site.
- Packaging status is structural. Build/test/provenance evidence belongs to the downstream baseline/release-gate beads and was not executed here.

Final confidence: high for OSS-present/stub/absent classifications in governance, routing, UI, Helm/config, and API layers; medium for deeper enterprise security/telemetry gaps that could be implemented under names outside the searched patterns.
