# Migration Compatibility Manifest

Status: architecture contract for `bif-cks.15`, not a claim that the current gateway already implements every control below.

This manifest defines the migration ID namespace, module dependency contract, rolling-upgrade matrix, Kubernetes predeploy migration job shape, mixed-version compatibility rules, and failure oracles required before Bifrost is run as an internally operated Kubernetes gateway on Aurora PostgreSQL. It is grounded in the current migration source and in `docs/roadmap/release/bif-kyy-14-1-release-audit.md`, which verified a clean-source build and targeted Go tests but did not verify Docker/Helm publishing, CI secrets, SBOM generation, artifact signing, live-provider release tests, or complete framework integration dependencies.

## Current Source Facts

- The shared migrator records applied migration IDs in a `migrations` table with `id`, `sequence`, `applied_at`, and `status` columns, uses transactions by default, and currently leaves unknown migration validation disabled in `DefaultOptions` (`framework/migrator/migrator.go:79`, `framework/migrator/migrator.go:162`, `framework/migrator/migrator.go:269`).
- `PendingIDs` is the current read-only preflight helper. If the migration table does not exist, or if older metadata columns are absent, it treats all expected IDs as pending (`framework/migrator/migrator.go:79`).
- Config-store migrations are startup-triggered, use PostgreSQL advisory lock `1000001`, retry every 5 seconds for up to 1 minute, and run from an ordered `configstoreMigrationSteps` list. PostgreSQL uses a throwaway migration pool with `default_query_exec_mode=simple_protocol` before opening the runtime pool (`framework/configstore/migrations.go:35`, `framework/configstore/migrations.go:272`, `framework/configstore/migrations.go:635`, `framework/configstore/postgres.go:17`, `framework/configstore/postgres.go:45`).
- Config-store SQLite migrations share the same DB handle and run the same step mechanism after local duplicate/null-key cleanup (`framework/configstore/sqlite.go:58`).
- Log-store migrations are startup-triggered, use PostgreSQL advisory lock `1000011`, retry every 5 seconds for up to 5 minutes, and run from `logstoreMigrationSteps`. Separate advisory locks protect asynchronous index creation and materialized-view refresh (`framework/logstore/migrations.go:35`, `framework/logstore/migrations.go:214`, `framework/logstore/migrations.go:292`).
- Log-store PostgreSQL requires PostgreSQL 16+, closes its migration pool before opening the runtime pool, and starts index and materialized-view maintenance goroutines after startup. Failures in those goroutines are warnings; dashboard paths fall back to raw tables when materialized views are not ready (`framework/logstore/postgres.go:131`, `framework/logstore/postgres.go:190`, `framework/logstore/postgres.go:202`).
- Materialized-view maintenance already carries a rolling-deploy warning: a view must only be added to the legacy drop list after a release has shipped that stops reading from it, because same-release removal can break old replicas (`framework/logstore/matviews.go:93`, `framework/logstore/matviews.go:414`, `framework/logstore/matviews.go:690`, `framework/logstore/matviews.go:809`).

## Migration ID Namespace

All new migrations must use globally unique, namespaced IDs:

```text
<module>/<stream>/<yyyymmddhhmmss>-<slug>
```

Examples:

```text
configstore/core/20260715120000-add-team-entitlement-cache
logstore/schema/20260715120500-add-redaction-policy-columns
logstore/index/20260715121000-add-log-metadata-gin-marker
logstore/matview/20260715121500-split-filter-data-v2
plugin.governance/config/20260715122000-add-budget-reservations
enterprise/okta/20260715122500-add-entitlement-snapshot-version
```

Reserved namespaces:

| Namespace | Owner | Allowed Work |
| --- | --- | --- |
| `configstore/core` | `framework/configstore` | Provider config, virtual keys, teams, customers, budgets, governance control-plane records. |
| `logstore/schema` | `framework/logstore` | Request logs, MCP tool logs, async jobs, redaction metadata, API-visible log schema. |
| `logstore/index` | `framework/logstore` | Metadata markers for index lifecycle; heavy index builds stay outside startup transactions. |
| `logstore/matview` | `framework/logstore` | Materialized-view shape and retirement gates. |
| `plugin.<name>/config` | Plugin module | Plugin-owned config tables or columns. |
| `plugin.<name>/log` | Plugin module | Plugin-owned log/audit tables or columns. |
| `enterprise/<domain>` | Enterprise module | Okta, entitlement, privacy, policy, or other enterprise-only schema. |
| `compat/legacy` | Migration manifest only | Alias namespace for existing unnamespaced IDs already shipped in databases. |

Legacy IDs already present in source must remain immutable in the database. They may be documented with `compat/legacy` aliases, but the value stored in `migrations.id` must never be rewritten. New code must not introduce additional bare IDs such as `init` or `add_foo_column`.

Each ID gets exactly one manifest entry, even when a single source function records multiple IDs. Current duplicate-looking legacy IDs in config-store step declarations prove why the validation must run at the manifest/source level rather than relying only on per-`gormigrate` duplicate detection.

Immutable ID rules:

- Never edit, reorder, delete, or repurpose a shipped migration ID.
- Never reuse a slug after a failed or reverted merge request; create a new timestamped ID.
- Never use branch-local names such as `test`, `tmp`, `fix`, or `migration2`.
- Destructive migrations must carry a retirement release and a last-compatible application version.

## Module Dependency Manifest

Each release must publish a machine-checkable manifest with this shape:

```yaml
manifest_version: 1
source_commit: "<git sha>"
image_digest: "<immutable image digest>"
release: "<semver or internal release id>"
schema_epoch: "<monotonic release schema epoch>"

modules:
  configstore:
    namespace: "configstore/core"
    advisory_lock: 1000001
    lock_timeout: "1m"
    phase: "predeploy-required"
    owns:
      - provider and key configuration
      - virtual keys, teams, customers, budgets, rate limits
      - governance and control-plane records
    before:
      - transports/bifrost-http
      - plugin.governance
      - enterprise/okta

  logstore:
    namespace: "logstore/schema"
    advisory_lock: 1000011
    lock_timeout: "5m"
    phase: "predeploy-required"
    owns:
      - request logs
      - MCP tool logs
      - async jobs
      - redaction fields
    post_start_maintenance:
      - lock: 1000012
        namespace: "logstore/index"
      - lock: 1000015
        namespace: "logstore/matview"

migrations:
  - id: "configstore/core/20260715120000-add-team-entitlement-cache"
    legacy_id: null
    module: "configstore"
    source: "framework/configstore/migrations.go:<function>"
    phase: "predeploy"
    class: "additive-nullable"
    requires_schema_epoch: "N"
    produces_schema_epoch: "N+1"
    compatible_readers: ["N", "N+1"]
    compatible_writers: ["N", "N+1"]
    rollback: "forward-compatible-code-rollback"
    heavy_ddl: false
    data_backfill: "none"
    failure_oracles:
      - "N binary starts against N+1 schema"
      - "N+1 binary refuses to serve if this ID is pending"
```

Dependency rules:

- Config-store schema required by auth, virtual keys, budgets, provider selection, or Okta entitlements must be available before any new HTTP transport or governance plugin path is enabled.
- Log-store schema may evolve independently, but API readers must keep raw-table fallbacks until all materialized-view readers from the previous release are retired.
- Plugin migrations must declare their owner module and the core schema epochs they require; plugin code may not implicitly depend on unmanifested config-store or log-store columns.
- A module may only read another module's new columns when the producing migration declares `compatible_readers` for that consuming application version.
- Cross-module backfills must have a single coordinator module and must not be split across independent startup paths.

## Compatibility Classes

| Class | Same-Release Rolling Deploy | Rollback to N Code | Requirements |
| --- | --- | --- | --- |
| `additive-nullable` | Allowed | Allowed | New nullable/defaulted columns or tables; old code ignores them. |
| `additive-dual-write` | Allowed with feature gate | Allowed while dual-write remains active | N+1 writes old and new shapes; N and N+1 readers both succeed. |
| `backfill-forward` | Allowed only after oracle pass | Code rollback allowed, data downgrade not assumed | Backfill is idempotent and forward-compatible; old code tolerates upgraded rows. |
| `async-maintenance` | Allowed outside startup path | Allowed | Indexes/materialized views are optional acceleration paths with raw fallback. |
| `destructive-retire` | Not allowed in same release | Not rollbackable without restore or verified reverse migration | Requires at least one release where nobody reads/writes the old shape. |
| `breaking-contract` | Prohibited | Prohibited | Required new request fields, enum narrowing, incompatible snapshots, relation drops used by N. |

Current rollback functions are not a release safety guarantee. Unless a migration has a tested reverse transform and rollback oracle, operational rollback means rolling code back while keeping the upgraded schema.

## N/N+1/Rollback Matrix

| Scenario | Expected Result | Gate |
| --- | --- | --- |
| N app on N schema | Serves normally. | Existing release tests. |
| N+1 predeploy job on N schema | Applies only manifest-declared predeploy migrations and exits with an auditable summary. | Job exit code 0 and schema epoch reaches N+1. |
| N+1 app on N schema with required migrations pending | Refuses readiness and does not serve inference or control-plane writes. | Startup oracle. |
| N app on N+1 additive schema | Serves normally and ignores new columns/tables. | Rollback smoke test. |
| N app on N+1 destructive schema | Release is invalid. | Manifest linter rejects `destructive-retire` without prior retirement release. |
| N+1 writer with N reader | Allowed only for additive/dual-write classes. | Mixed-version API/event/snapshot tests. |
| N+1 reader with N writer | Reader must tolerate missing optional fields and old enum values. | Mixed-version API/event/snapshot tests. |
| N+1 migration job fails before changes | Rollout is blocked; N pods continue. | Kubernetes job failure and deployment wave gate. |
| N+1 migration job fails after partial forward-compatible changes | Rollout is blocked; operator follows migration-specific recovery notes; N pods must still pass rollback smoke. | Partial-failure oracle. |
| Rollback N+1 code to N after successful predeploy | Allowed only when N binary has passed against N+1 schema. | Rollback oracle required before release. |
| Rollback after backfill | Code rollback may be allowed; data downgrade is not assumed. | Backfill manifest must say `forward-only` or provide tested reverse transform. |

## Predeploy Kubernetes Migration Job

The launch target should move required PostgreSQL migrations out of normal pod startup and into a predeploy Job. Existing startup migration code remains useful as a compatibility verifier, but application pods should not race each other to perform schema changes during rollout when predeploy mode is enabled.

Prototype shape:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: bifrost-migrate-<release>
  labels:
    app.kubernetes.io/name: bifrost
    app.kubernetes.io/component: migration
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 900
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: bifrost-migration
      containers:
        - name: migrate
          image: "<same immutable digest as N+1 app image>"
          command:
            - bifrost-http
            - migrate
            - --manifest=/app/migration-compatibility.yaml
            - --target-schema-epoch=$(BIFROST_SCHEMA_EPOCH)
            - --phase=predeploy
          envFrom:
            - secretRef:
                name: bifrost-database
```

The `bifrost-http migrate` command is a required future entrypoint, not verified current functionality.

Job requirements:

- Use the same immutable image digest and source commit as the application release.
- Mount database credentials only; provider keys, Okta secrets, signing keys, and publishing credentials are not needed.
- Acquire the same module advisory locks used by runtime migrators.
- Validate the manifest hash, source commit, database dialect, PostgreSQL version, pending IDs, duplicate IDs, unknown IDs, and compatibility class before mutation.
- Apply only `phase: predeploy` migrations. `logstore/index` and `logstore/matview` maintenance remains post-start and must have raw fallbacks.
- Emit an operator-readable summary: source commit, image digest, module, pending IDs, applied IDs, skipped IDs, lock wait, duration, schema epoch, and failure reason.
- Exit nonzero on any failed oracle. A failed job blocks the deployment wave while old pods remain serving.

Startup behavior after this job:

- Application pods run a verify-only check for required schema epoch and manifest compatibility.
- If required migrations are still pending, readiness stays false and serving paths do not open.
- Optional asynchronous maintenance may begin only after serving schema requirements pass.

## Mixed-Version Compatibility

Events and snapshots:

- Every durable event, outbox message, entitlement snapshot, budget snapshot, privacy/eval trace envelope, and MCP governance record must carry `schema_version`, `producer_version`, and a monotonic source revision when applicable.
- N consumers must either parse N+1 records or N+1 producers must continue publishing an N-compatible envelope until the fleet minimum version has advanced.
- New fields are optional for at least one release. Field removal, rename, enum narrowing, and required-field introduction are prohibited during rolling deploy.
- Dual-write is required when old readers still depend on the old shape.
- Unknown enum values must be treated as opaque or policy-denied, not as parser failures.

HTTP and management APIs:

- Request changes are additive and optional during N/N+1. No same-release required request fields.
- Response changes are additive; old clients must tolerate unknown fields.
- New filters, routing modes, MCP policy states, budget overdraft states, or privacy trace states must have default behavior that old pods can safely ignore or deny.
- API handlers reading materialized views must retain raw-table fallbacks until the previous release no longer reads the old view shape.

Config and control-plane records:

- Persisted config must remain readable by N and N+1 during rolling deploy.
- New config fields default to the old behavior when absent.
- Feature gates must not switch a code path to read a future-only column before the migration job has succeeded and the startup oracle has passed.
- Provider routing, virtual-key budget enforcement, and Okta entitlement checks must fail closed when a required schema version or snapshot version is unavailable.

## Startup Failure Oracles

A pod must refuse readiness when any of these checks fail:

- Required schema epoch is missing or lower than the application manifest requires.
- A required migration ID is pending after predeploy mode should have completed.
- Manifest contains duplicate IDs, bare new IDs, unknown unapplied IDs, or a source hash mismatch.
- PostgreSQL advisory lock acquisition times out while a required startup migration is still configured.
- The migration metadata table is missing required columns after bootstrap.
- PostgreSQL version is below a module requirement, including the current log-store PostgreSQL 16+ requirement.
- A migration attempts heavy startup DDL that belongs in `async-maintenance`.
- A materialized-view or index maintenance failure removes the raw-table fallback path.
- Config-store, log-store, or plugin manifests disagree about schema epoch or dependency ordering.

Warnings that must not block serving when raw fallbacks are intact:

- Optional performance index creation is already held by another pod.
- Materialized-view refresh is already held by another pod.
- Dashboard acceleration is unavailable but raw log queries still pass.

## Rollback Failure Oracles

Before a release is allowed to roll out:

- The N binary must start against the N+1 schema produced by the predeploy job.
- N management APIs must read representative N+1 config records without parse failures.
- N log APIs must read representative N+1 log rows or use raw fallback paths.
- N routing, virtual-key, budget, and entitlement paths must either preserve old behavior or fail closed.
- N MCP governance paths must tolerate N+1 tool policy records or deny unknown policy states.
- N privacy trace/eval readers must ignore optional N+1 fields and reject only explicitly incompatible versions.
- Any migration marked `destructive-retire` must prove the previous release stopped reading and writing the retired shape.
- Any backfill marked reversible must include a tested reverse transform; otherwise it is forward-only and rollback cannot promise data downgrade.

Rollback must be blocked when the only recovery path is restoring Aurora from backup, unless the release is explicitly approved as non-rollbackable.

## Validation Gates

Required next implementation gates:

- Static extractor over current migration source that emits every `IDs` entry from config-store and log-store migration steps.
- Manifest linter enforcing global uniqueness, namespace format for new IDs, legacy aliasing, advisory-lock ownership, phase validity, and compatibility class requirements.
- Source linter rejecting heavy startup DDL, same-release materialized-view drops used by old readers, missing raw fallbacks, and unmanifested cross-module reads.
- Matrix test harness that runs N app/N schema, N+1 app/N schema before migration, N+1 app/N+1 schema, and N app/N+1 schema.
- Mixed-version fixtures for control-plane APIs, durable events, snapshots, MCP governance records, budget overdraft records, and privacy/eval trace envelopes.
- Kubernetes dry-run for the migration Job with no provider or publishing secrets mounted.
- Release audit extension that records the migration manifest hash, image digest, applied IDs, rollback smoke result, and exact pass/fail evidence.

The current release audit does not verify enough surfaces to claim migration readiness. Until these gates exist, startup migration behavior remains a known operational dependency rather than a proven rolling-upgrade contract.

## Assumptions

- Aurora PostgreSQL is the enterprise launch database for shared control-plane and log-store state.
- Redis is optional and must not be required for migration convergence or rollback safety.
- Application availability depends on inference/provider/plugin hot paths staying outside optional learning, evaluation, or autonomous promotion services.
- Git merge requests remain the only promotion channel before launch; the gateway may propose issues, patches, or draft merge requests, but must not merge or publish.
- Existing legacy migration IDs are already present in some environments and cannot be rewritten safely.

## Open Questions

- Which artifact will own the first machine-readable manifest: repository file, generated release asset, Helm value, or image-embedded metadata?
- Should the migration metadata table remain shared as `migrations`, or should modules move to module-specific metadata tables while retaining legacy reads?
- What exact schema epoch naming should match internal release trains?
- Which N release is the first rollback baseline for the N/N+1 harness?
- Should SQLite remain covered by the same manifest, or be explicitly classified as local/dev-only for enterprise launch?
