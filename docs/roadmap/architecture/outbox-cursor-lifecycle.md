# Aurora Outbox Cursor Lifecycle

Status: architecture design for `bif-kyy.6.8`
Scope: internal enterprise Kubernetes launch with Aurora PostgreSQL authority
Non-goal: add Redis, gossip, peer state transfer, or any per-request control-plane read to the inference path

## Decision

Bifrost control-plane mutations should publish compact domain events into an Aurora
PostgreSQL transactional outbox in the same transaction as the authority-row update.
Gateway pods consume those events into immutable local snapshots. PostgreSQL
`LISTEN/NOTIFY` is only a wakeup path; durable cursor polling is the correctness path.

Every ready pod proves:

1. It has installed a signed snapshot watermark at or beyond the required freshness
   lease for each authority domain it serves.
2. Its consumer lease is alive, or it is intentionally serving only bounded-fresh
   last-known-good state.
3. Any poisoned event affecting a tenant/resource is represented in local policy as a
   safe failure disposition before the consumer cursor advances past it.

Inference reads only the local installed snapshot. Aurora, notification listeners,
compaction, resnapshot workers, and evidence generation stay outside the request path.

## Resource Classes

Use one outbox mechanism for low/medium-rate authority changes:

- virtual keys, key revocation, emergency rotation;
- Okta-derived users, groups, group membership, access profiles;
- routing rules, provider/key policy, model visibility;
- MCP client catalog, grants, kill switches;
- privacy/evidence policy revisions;
- budget policy and overdraft-policy changes.

Do not use this outbox for high-rate spend counter increments. Budget reservations and
settlement need their own ledger/counter authority. The outbox can publish budget policy
changes and reservation-service configuration, not every token charge.

## Timing Defaults

These are initial product defaults to validate in Aurora and Kubernetes failure tests,
not measured benchmark claims.

| Setting | Default | Reason |
|---|---:|---|
| Poll interval while healthy | 1s plus 0-250ms jitter | Meets the 1-5 second policy convergence target without relying on notifications. |
| Poll interval after listener failure | 1s plus 0-500ms jitter | Listener loss must not degrade correctness. |
| Poll interval when caught up for 5 minutes | 2s plus 0-500ms jitter | Reduces idle Aurora reads while preserving the convergence target. |
| Listener reconnect backoff | 250ms min, 5s max, full jitter | Aurora failover and network resets are expected. |
| Consumer lease duration | 20s, DB-time based | Avoids pod clock skew and gives compaction a retirement oracle. |
| Consumer lease renewal | every 5s | Leaves multiple renewal attempts before expiry. |
| Readiness grace after lease renewal failure | 2 failed renewals or snapshot lease expiry, whichever comes first | Avoids flapping on transient errors while bounding stale authority. |
| Security-reduction freshness lease | 15s | Revocations, deny rules, and policy reductions fail closed after this age. |
| Stable config freshness lease | 5m | Provider/routing config can remain usable longer than security reductions. |
| Outbox event retention floor | 48h | Gives down pods time to catch up; pods older than this resnapshot. |
| Snapshot retention floor | 7d or last 3 signed watermarks per domain, whichever is larger | Supports rollback and mixed-version rollout. |
| Poison retry attempts | 5 attempts with exponential backoff capped at 5m | Separates transient decode/database errors from malformed events. |
| Tenant fairness batch | 64 tenants per drain pass, 100 events per tenant, high-risk events first | Prevents one hot tenant from starving quiet tenants. |
| Consumer retirement grace | lease expiry plus 2m | Prevents dead pods from blocking compaction indefinitely. |

## Schema Pseudocode

Names are illustrative. The implementation can place these in the existing configstore
migration owner, but the tables should remain domain-neutral and versioned.

### Outbox Events

Events are immutable. Avoid per-event status updates on the hot outbox table; poison,
attempt, cursor, and compaction state live in side tables.

```sql
CREATE TABLE bifrost_control_outbox (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id           TEXT NOT NULL,
  domain              TEXT NOT NULL,
  resource_id         TEXT NOT NULL,
  resource_revision   BIGINT NOT NULL,
  operation           TEXT NOT NULL,
  risk_class          TEXT NOT NULL,
  schema_version      INTEGER NOT NULL,
  idempotency_key     TEXT NOT NULL,
  payload_ref         JSONB NOT NULL DEFAULT '{}'::jsonb,
  checksum_sha256     BYTEA NOT NULL,
  actor_id            TEXT,
  reason              TEXT,
  trace_id            TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

  CONSTRAINT bifrost_outbox_domain_op_chk
    CHECK (operation IN ('create', 'update', 'delete', 'rotate', 'deny', 'snapshot_hint')),
  CONSTRAINT bifrost_outbox_risk_chk
    CHECK (risk_class IN ('security_reduction', 'security_increase', 'spend_reduction',
                          'spend_increase', 'routing', 'mcp', 'privacy', 'ops')),
  CONSTRAINT bifrost_outbox_resource_revision_uniq
    UNIQUE (domain, resource_id, resource_revision),
  CONSTRAINT bifrost_outbox_idempotency_uniq
    UNIQUE (idempotency_key)
) PARTITION BY RANGE (created_at);

CREATE INDEX bifrost_outbox_id_idx
  ON bifrost_control_outbox (id);

CREATE INDEX bifrost_outbox_tenant_id_idx
  ON bifrost_control_outbox (tenant_id, id);

CREATE INDEX bifrost_outbox_domain_resource_idx
  ON bifrost_control_outbox (domain, resource_id, resource_revision);

CREATE INDEX bifrost_outbox_risk_id_idx
  ON bifrost_control_outbox (risk_class, id);
```

Partition by time, and optionally hash-subpartition by `tenant_id` if realistic launch
data shows a few tenants dominate event volume. Drop or detach old partitions for
compaction rather than issuing large deletes against the parent table.

### Consumer Leases

Consumer rows are ephemeral and DB-time based. `consumer_id` should include the pod name
and Kubernetes pod UID. `generation_id` changes on every process start to fence stale
updates from a previous process with the same pod name.

```sql
CREATE TABLE bifrost_outbox_consumers (
  consumer_id                 TEXT PRIMARY KEY,
  generation_id               UUID NOT NULL,
  pod_name                    TEXT NOT NULL,
  pod_uid                     TEXT NOT NULL,
  build_version               TEXT NOT NULL,
  reader_schema_version       INTEGER NOT NULL,
  state                       TEXT NOT NULL,
  started_at                  TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  heartbeat_at                TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  lease_expires_at            TIMESTAMPTZ NOT NULL,
  fencing_token               BIGINT NOT NULL DEFAULT 1,
  cursor_outbox_id            BIGINT NOT NULL DEFAULT 0,
  installed_watermark_id      UUID,
  installed_watermark_outbox_id BIGINT NOT NULL DEFAULT 0,
  listener_status             TEXT NOT NULL DEFAULT 'unknown',
  last_notify_at              TIMESTAMPTZ,
  last_poll_at                TIMESTAMPTZ,
  last_drained_at             TIMESTAMPTZ,
  last_error                  TEXT,
  retired_at                  TIMESTAMPTZ,

  CONSTRAINT bifrost_consumer_state_chk
    CHECK (state IN ('active', 'draining', 'expired', 'retired'))
);

CREATE INDEX bifrost_consumers_active_cursor_idx
  ON bifrost_outbox_consumers (cursor_outbox_id)
  WHERE state = 'active';

CREATE INDEX bifrost_consumers_lease_idx
  ON bifrost_outbox_consumers (lease_expires_at)
  WHERE state IN ('active', 'draining');
```

Because this table is updated frequently, configure it for HOT-friendly updates:

```sql
ALTER TABLE bifrost_outbox_consumers
  SET (fillfactor = 70,
       autovacuum_vacuum_scale_factor = 0.01,
       autovacuum_analyze_scale_factor = 0.02,
       autovacuum_vacuum_threshold = 50,
       autovacuum_analyze_threshold = 50);
```

### Tenant Cursors

The global cursor protects compaction. Tenant/domain cursors protect fairness and
tenant-specific freshness. A tenant can be current even when another tenant is waiting
on a poison event or resnapshot.

```sql
CREATE TABLE bifrost_outbox_tenant_cursors (
  consumer_id        TEXT NOT NULL REFERENCES bifrost_outbox_consumers(consumer_id)
    ON DELETE CASCADE,
  tenant_id          TEXT NOT NULL,
  domain             TEXT NOT NULL,
  cursor_outbox_id   BIGINT NOT NULL DEFAULT 0,
  resource_revision  BIGINT NOT NULL DEFAULT 0,
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (consumer_id, tenant_id, domain)
);

CREATE INDEX bifrost_tenant_cursor_lag_idx
  ON bifrost_outbox_tenant_cursors (tenant_id, domain, cursor_outbox_id);
```

### Signed Snapshot Watermarks

A snapshot watermark is the durable proof that a normalized authority snapshot was read,
validated, checksummed, and signed. The signature covers the manifest, resource counts,
schema versions, upper outbox ID, previous watermark, and freshness leases. The gateway
can persist the full manifest in Aurora JSONB or in versioned object storage; Aurora
still owns the watermark row.

```sql
CREATE TABLE bifrost_snapshot_watermarks (
  id                    UUID PRIMARY KEY,
  tenant_id             TEXT,
  snapshot_kind         TEXT NOT NULL,
  domains               TEXT[] NOT NULL,
  upper_outbox_id       BIGINT NOT NULL,
  tenant_revisions      JSONB NOT NULL DEFAULT '{}'::jsonb,
  manifest_uri          TEXT,
  manifest_sha256       BYTEA NOT NULL,
  manifest_bytes        JSONB,
  signature_alg         TEXT NOT NULL,
  signature_key_id      TEXT NOT NULL,
  signature             BYTEA NOT NULL,
  producer_id           TEXT NOT NULL,
  reader_min_version    INTEGER NOT NULL,
  reader_max_version    INTEGER NOT NULL,
  produced_at           TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  expires_at            TIMESTAMPTZ NOT NULL,
  previous_watermark_id UUID,
  status                TEXT NOT NULL DEFAULT 'active',

  CONSTRAINT bifrost_watermark_status_chk
    CHECK (status IN ('active', 'superseded', 'revoked', 'rollback'))
);

CREATE INDEX bifrost_watermark_lookup_idx
  ON bifrost_snapshot_watermarks (snapshot_kind, tenant_id, upper_outbox_id DESC);
```

The signing key should be a KMS-backed asymmetric key or an HMAC key held outside the
gateway process. Runtime pods verify signatures; they do not mint launch-authority
watermarks.

### Poison Quarantine

Poison state is separate from outbox events. Quarantine is a control-plane decision with
a safe local disposition; it is not silent event loss.

```sql
CREATE TABLE bifrost_outbox_poison (
  event_id              BIGINT PRIMARY KEY REFERENCES bifrost_control_outbox(id),
  tenant_id             TEXT NOT NULL,
  domain                TEXT NOT NULL,
  resource_id           TEXT NOT NULL,
  first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  last_seen_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  attempts              INTEGER NOT NULL DEFAULT 1,
  next_attempt_at       TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  error_class           TEXT NOT NULL,
  error_digest          TEXT NOT NULL,
  quarantine_policy     TEXT,
  quarantined_at        TIMESTAMPTZ,
  repaired_by_watermark UUID,
  status                TEXT NOT NULL DEFAULT 'retrying',

  CONSTRAINT bifrost_poison_status_chk
    CHECK (status IN ('retrying', 'quarantined', 'repaired', 'ignored_by_policy'))
);

CREATE INDEX bifrost_poison_open_idx
  ON bifrost_outbox_poison (status, next_attempt_at);
```

### Resnapshot Requests

Resnapshot requests are durable work items. They are created by consumers, operators, or
rollout jobs when event replay cannot safely continue.

```sql
CREATE TABLE bifrost_resnapshot_requests (
  id                    UUID PRIMARY KEY,
  tenant_id             TEXT,
  domains               TEXT[] NOT NULL,
  requested_upper_id    BIGINT NOT NULL,
  reason                TEXT NOT NULL,
  requested_by          TEXT NOT NULL,
  requested_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  lease_holder          TEXT,
  lease_expires_at      TIMESTAMPTZ,
  completed_watermark_id UUID,
  status                TEXT NOT NULL DEFAULT 'pending',
  error                 TEXT,

  CONSTRAINT bifrost_resnapshot_status_chk
    CHECK (status IN ('pending', 'running', 'complete', 'failed', 'cancelled'))
);

CREATE INDEX bifrost_resnapshot_pending_idx
  ON bifrost_resnapshot_requests (status, requested_at);
```

## Mutation Publication

Every authority mutation writes its domain row and an outbox event in one transaction.
Call `pg_notify` inside the same transaction so notification delivery is coupled to
commit. The notify payload is a hint, not authority.

```sql
BEGIN;

UPDATE governance_virtual_keys
SET is_active = false,
    updated_at = clock_timestamp(),
    revision = revision + 1
WHERE id = $1
RETURNING tenant_id, id, revision;

INSERT INTO bifrost_control_outbox (
  tenant_id,
  domain,
  resource_id,
  resource_revision,
  operation,
  risk_class,
  schema_version,
  idempotency_key,
  payload_ref,
  checksum_sha256,
  actor_id,
  reason
) VALUES (
  $tenant_id,
  'virtual_key',
  $vk_id,
  $revision,
  'update',
  'security_reduction',
  1,
  $idempotency_key,
  jsonb_build_object('authority_table', 'governance_virtual_keys', 'id', $vk_id),
  digest($canonical_event_payload, 'sha256'),
  $actor_id,
  $reason
)
RETURNING id INTO $outbox_id;

SELECT pg_notify(
  'bifrost_control_outbox',
  json_build_object(
    'max_id', $outbox_id,
    'tenant_id', $tenant_id,
    'domain', 'virtual_key'
  )::text
);

COMMIT;
```

If the process crashes after commit, polling still finds the row. If notification is
dropped during Aurora failover, polling still finds the row. If the transaction rolls
back, neither the authority mutation nor the outbox event exists.

## Consumer Lifecycle

### Register

On startup, a pod registers a new generation. A pod with no verified initial snapshot
is not ready. Registration uses DB time only.

```sql
INSERT INTO bifrost_outbox_consumers (
  consumer_id,
  generation_id,
  pod_name,
  pod_uid,
  build_version,
  reader_schema_version,
  state,
  lease_expires_at
) VALUES (
  $consumer_id,
  $generation_id,
  $pod_name,
  $pod_uid,
  $build_version,
  $reader_schema_version,
  'active',
  clock_timestamp() + interval '20 seconds'
)
ON CONFLICT (consumer_id) DO UPDATE
SET generation_id = EXCLUDED.generation_id,
    pod_uid = EXCLUDED.pod_uid,
    build_version = EXCLUDED.build_version,
    reader_schema_version = EXCLUDED.reader_schema_version,
    state = 'active',
    started_at = clock_timestamp(),
    heartbeat_at = clock_timestamp(),
    lease_expires_at = clock_timestamp() + interval '20 seconds',
    fencing_token = bifrost_outbox_consumers.fencing_token + 1,
    last_error = NULL,
    retired_at = NULL
WHERE bifrost_outbox_consumers.state IN ('expired', 'retired')
   OR bifrost_outbox_consumers.lease_expires_at < clock_timestamp()
RETURNING fencing_token;
```

If the `ON CONFLICT` update returns no row, another live generation owns the consumer ID.
The pod must pick a unique ID or remain unready.

### Renew

Renewal proves the consumer generation is still alive. A failed renewal makes the pod
stop publishing readiness before it loses the ability to serve from a stale snapshot.

```sql
UPDATE bifrost_outbox_consumers
SET heartbeat_at = clock_timestamp(),
    lease_expires_at = clock_timestamp() + interval '20 seconds',
    fencing_token = fencing_token + 1,
    listener_status = $listener_status,
    last_poll_at = $last_poll_at,
    last_notify_at = COALESCE($last_notify_at, last_notify_at),
    last_error = NULL
WHERE consumer_id = $consumer_id
  AND generation_id = $generation_id
  AND state = 'active'
  AND lease_expires_at > clock_timestamp()
RETURNING fencing_token, cursor_outbox_id, installed_watermark_outbox_id;
```

If no row is returned, the process is fenced. It must mark itself unready, stop applying
events, and re-register with a fresh generation.

### Listen And Poll

Each pod runs one dedicated listener connection and one polling loop. The listener calls
`LISTEN bifrost_control_outbox`; notification receipt wakes the drain loop immediately.
The poller still runs on schedule and compares the local cursor with durable Aurora state.

```sql
SELECT max(id) AS max_outbox_id
FROM bifrost_control_outbox;
```

Do not place authority payloads in notify messages. A valid notify payload is at most a
wakeup and optional diagnostics: `max_id`, `tenant_id`, `domain`. Consumers ignore
payload ordering and drain from their durable cursor.

### Fair Drain

The drain loop prioritizes high-risk security/spend reductions while preventing hot
tenants from starving quiet tenants. Events remain ordered per tenant/domain/resource.

```sql
WITH pending_tenants AS (
  SELECT e.tenant_id,
         min(e.id) AS first_pending_id,
         bool_or(e.risk_class IN ('security_reduction', 'spend_reduction')) AS has_high_risk
  FROM bifrost_control_outbox e
  LEFT JOIN bifrost_outbox_tenant_cursors c
    ON c.consumer_id = $consumer_id
   AND c.tenant_id = e.tenant_id
   AND c.domain = e.domain
  WHERE e.id > COALESCE(c.cursor_outbox_id, 0)
    AND e.id <= $target_max_id
  GROUP BY e.tenant_id
  ORDER BY has_high_risk DESC, first_pending_id ASC
  LIMIT 64
),
tenant_batches AS (
  SELECT e.*
  FROM pending_tenants t
  CROSS JOIN LATERAL (
    SELECT *
    FROM bifrost_control_outbox e
    WHERE e.tenant_id = t.tenant_id
      AND e.id <= $target_max_id
    ORDER BY
      CASE WHEN e.risk_class IN ('security_reduction', 'spend_reduction') THEN 0 ELSE 1 END,
      e.id
    LIMIT 100
  ) e
)
SELECT *
FROM tenant_batches
ORDER BY
  CASE WHEN risk_class IN ('security_reduction', 'spend_reduction') THEN 0 ELSE 1 END,
  id;
```

After successful application, update the per-tenant/domain cursor and the global
compaction cursor. The global cursor is the highest contiguous outbox ID that has either
been applied or safely represented by a quarantine/resnapshot disposition.

```sql
INSERT INTO bifrost_outbox_tenant_cursors (
  consumer_id, tenant_id, domain, cursor_outbox_id, resource_revision, updated_at
) VALUES (
  $consumer_id, $tenant_id, $domain, $cursor_outbox_id, $resource_revision, clock_timestamp()
)
ON CONFLICT (consumer_id, tenant_id, domain) DO UPDATE
SET cursor_outbox_id = GREATEST(bifrost_outbox_tenant_cursors.cursor_outbox_id,
                                EXCLUDED.cursor_outbox_id),
    resource_revision = GREATEST(bifrost_outbox_tenant_cursors.resource_revision,
                                 EXCLUDED.resource_revision),
    updated_at = clock_timestamp();

UPDATE bifrost_outbox_consumers
SET cursor_outbox_id = GREATEST(cursor_outbox_id, $global_contiguous_cursor),
    installed_watermark_id = $installed_watermark_id,
    installed_watermark_outbox_id = GREATEST(installed_watermark_outbox_id,
                                             $installed_watermark_outbox_id),
    last_drained_at = clock_timestamp()
WHERE consumer_id = $consumer_id
  AND generation_id = $generation_id
  AND state = 'active'
  AND lease_expires_at > clock_timestamp()
  AND fencing_token = $fencing_token;
```

If the final update affects zero rows, the consumer was fenced during application. It
must discard the candidate snapshot and re-register/resnapshot before serving.

## Snapshot And Watermark Lifecycle

### Build

Build snapshots from a repeatable-read view. The snapshot upper bound is the maximum
outbox ID visible inside that transaction. The manifest must be canonicalized before
hashing/signing.

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

SELECT COALESCE(max(id), 0)
FROM bifrost_control_outbox
WHERE tenant_id = COALESCE($tenant_id, tenant_id)
INTO $upper_outbox_id;

SELECT *
FROM governance_virtual_keys
WHERE tenant_id = COALESCE($tenant_id, tenant_id)
ORDER BY tenant_id, id;

SELECT *
FROM routing_rules
WHERE tenant_id = COALESCE($tenant_id, tenant_id)
ORDER BY tenant_id, priority, id;

-- Repeat for identity, MCP grants, privacy policy, provider policy, and budget policy.

COMMIT;
```

Then sign and insert the watermark:

```sql
INSERT INTO bifrost_snapshot_watermarks (
  id,
  tenant_id,
  snapshot_kind,
  domains,
  upper_outbox_id,
  tenant_revisions,
  manifest_uri,
  manifest_sha256,
  signature_alg,
  signature_key_id,
  signature,
  producer_id,
  reader_min_version,
  reader_max_version,
  expires_at,
  previous_watermark_id
) VALUES (
  $watermark_id,
  $tenant_id,
  $snapshot_kind,
  $domains,
  $upper_outbox_id,
  $tenant_revisions,
  $manifest_uri,
  $manifest_sha256,
  $signature_alg,
  $signature_key_id,
  $signature,
  $producer_id,
  $reader_min_version,
  $reader_max_version,
  clock_timestamp() + interval '7 days',
  $previous_watermark_id
);
```

### Install

A pod installs a snapshot only when:

- the signature verifies against an active trust root;
- the manifest hash matches;
- `reader_min_version <= pod_reader_version <= reader_max_version`;
- `upper_outbox_id` is not lower than the currently installed watermark, unless the
  watermark has `status = 'rollback'` and is signed by the emergency rollback key;
- every domain parser validates the manifest before publication;
- the local snapshot swap is atomic.

If any check fails, the pod keeps the last-known-good snapshot. If the relevant freshness
lease expires, it becomes unready and fails closed for affected authority classes.

### Resnapshot

Trigger resnapshot when:

- the pod's cursor is older than the compaction floor;
- a poison event is quarantined;
- the snapshot signature or manifest checksum fails;
- the pod boots with no local verified snapshot;
- a mixed-version rollout requires a compatibility-watermark refresh;
- operator requests a forced rebuild after incident response.

Resnapshot may be tenant/domain scoped. If tenant-scoped resnapshot is not possible
because the authority schema has cross-tenant invariants, perform a global snapshot and
record that decision in the request row.

## Poison Event Recovery

Poison handling must not silently skip authority changes.

1. Retry transient failures up to the configured attempt limit.
2. If retrying fails, insert or update `bifrost_outbox_poison`.
3. Apply a local safe disposition before advancing past the event:
   - security or spend reductions: fail closed for the affected tenant/resource class;
   - security or spend increases: ignore the increase until repaired;
   - routing/MCP/privacy changes: preserve last-known-good if still fresh, otherwise
     fail closed for affected operations.
4. Create a resnapshot request for the affected tenant/domain.
5. Alert with event ID, tenant, domain, resource ID, risk class, error digest, current
   safe disposition, and requested resnapshot ID.
6. Mark poison `repaired` only when a signed watermark at or beyond the poisoned event's
   outbox ID has been installed and validated.

Pseudocode:

```sql
INSERT INTO bifrost_outbox_poison (
  event_id,
  tenant_id,
  domain,
  resource_id,
  error_class,
  error_digest,
  next_attempt_at,
  status
) VALUES (
  $event_id,
  $tenant_id,
  $domain,
  $resource_id,
  $error_class,
  $error_digest,
  clock_timestamp() + $retry_backoff,
  'retrying'
)
ON CONFLICT (event_id) DO UPDATE
SET attempts = bifrost_outbox_poison.attempts + 1,
    last_seen_at = clock_timestamp(),
    next_attempt_at = clock_timestamp() + $retry_backoff,
    error_class = EXCLUDED.error_class,
    error_digest = EXCLUDED.error_digest;

UPDATE bifrost_outbox_poison
SET status = 'quarantined',
    quarantined_at = clock_timestamp(),
    quarantine_policy = $safe_disposition
WHERE event_id = $event_id
  AND attempts >= 5
  AND status = 'retrying';

INSERT INTO bifrost_resnapshot_requests (
  id, tenant_id, domains, requested_upper_id, reason, requested_by
) VALUES (
  gen_random_uuid(), $tenant_id, ARRAY[$domain], $event_id, 'poison_event', $consumer_id
)
ON CONFLICT DO NOTHING;
```

## Dead Consumer Retirement

Dead consumers must not block compaction forever. Retirement is based on Aurora DB time,
not pod clocks or Kubernetes watch state.

```sql
UPDATE bifrost_outbox_consumers
SET state = 'expired',
    retired_at = clock_timestamp(),
    last_error = 'lease expired'
WHERE state IN ('active', 'draining')
  AND lease_expires_at < clock_timestamp() - interval '2 minutes';

UPDATE bifrost_outbox_consumers
SET state = 'retired'
WHERE state = 'expired'
  AND retired_at < clock_timestamp() - interval '48 hours';
```

Kubernetes pod deletion can accelerate retirement only when pod UID matches and the
lease is already expired. Kubernetes is an observation source, not the durable truth.

A restarted pod with the same name but different `generation_id` must resnapshot or
resume from a signed local snapshot plus durable cursor. It cannot reuse an active lease
owned by an unexpired generation.

## Compaction

Compaction is safe only below the minimum active cursor and outside the retention floor.
Open poison rows pin affected partitions or require resnapshot before deletion.

```sql
WITH active_consumers AS (
  SELECT cursor_outbox_id
  FROM bifrost_outbox_consumers
  WHERE state = 'active'
    AND lease_expires_at > clock_timestamp()
),
floor AS (
  SELECT COALESCE(min(cursor_outbox_id), (SELECT COALESCE(max(id), 0) FROM bifrost_control_outbox)) AS cursor_floor
  FROM active_consumers
),
retention AS (
  SELECT COALESCE(max(id), 0) AS retention_floor
  FROM bifrost_control_outbox
  WHERE created_at < clock_timestamp() - interval '48 hours'
)
SELECT LEAST(floor.cursor_floor, retention.retention_floor) AS compact_through_id
FROM floor, retention;
```

For partitioned outbox:

```sql
-- Only when partition max(id) <= compact_through_id and no open poison rows reference it.
ALTER TABLE bifrost_control_outbox DETACH PARTITION bifrost_control_outbox_2026_07_15;
DROP TABLE bifrost_control_outbox_2026_07_15;
```

For non-partitioned early development environments:

```sql
DELETE FROM bifrost_control_outbox e
WHERE e.id <= $compact_through_id
  AND e.created_at < clock_timestamp() - interval '48 hours'
  AND NOT EXISTS (
    SELECT 1
    FROM bifrost_outbox_poison p
    WHERE p.event_id = e.id
      AND p.status IN ('retrying', 'quarantined')
  )
LIMIT 10000;
```

Production should prefer partition drop/detach. Large deletes create WAL, dead tuples,
replica lag, and autovacuum pressure.

If a pod returns after its cursor was compacted, it must install the newest compatible
signed snapshot and then drain events after the snapshot watermark. This is expected,
not an incident, if within retention policy.

## Per-Tenant Fairness

Fairness is a correctness property for internal multi-team use: a flood of routing edits
for one tenant must not delay revocation for another tenant.

Rules:

- Security and spend reductions are always high-priority within each drain pass.
- Each pass selects a bounded number of tenants and a bounded number of events per tenant.
- Tenant/domain cursors determine tenant freshness. Global cursor only determines
  compaction eligibility.
- A poison event for tenant A cannot block tenant B once tenant A has a safe quarantine
  disposition.
- Consumers expose lag by tenant/domain so operators can see unfairness directly.

Required metrics:

- `bifrost_outbox_tenant_lag_events{tenant,domain}`;
- `bifrost_outbox_tenant_lag_seconds{tenant,domain}`;
- `bifrost_outbox_high_risk_lag_seconds{tenant,domain,risk_class}`;
- `bifrost_outbox_fairness_skipped_tenants_total`;
- `bifrost_outbox_drain_batch_events{tenant,domain}`;
- `bifrost_snapshot_freshness_seconds{tenant,domain}`.

## LISTEN/NOTIFY Versus Polling

`LISTEN/NOTIFY` is an optimization:

- one dedicated listener connection per pod;
- payload contains only diagnostics;
- reconnect uses jittered backoff;
- notifications are ignored if malformed;
- every notification merely wakes the same durable drain loop used by polling.

Polling is authority:

- poll by durable outbox IDs and signed watermarks;
- polling continues during listener outage;
- polling catches events after Aurora failover and missed notifications;
- polling is what proves cursor lag and freshness leases.

Failure rules:

- Listener down, polling healthy: pod can remain ready if snapshots are fresh.
- Polling down, listener healthy: pod eventually becomes unready when freshness leases
  expire, because notify is not durable authority.
- Aurora unavailable: pod serves last-known-good until resource freshness leases expire;
  brand-new pods with no verified snapshot remain unready.

## WAL, Bloat, And Autovacuum Oracles

Track database health with both PostgreSQL native views and gateway metrics. Alert on
trends and lease/freshness impact rather than one isolated counter.

PostgreSQL metrics:

```sql
-- WAL pressure.
SELECT wal_records, wal_fpi, wal_bytes, wal_buffers_full
FROM pg_stat_wal;

-- Outbox and cursor table bloat indicators.
SELECT relname,
       n_live_tup,
       n_dead_tup,
       n_mod_since_analyze,
       vacuum_count,
       autovacuum_count,
       analyze_count,
       autoanalyze_count,
       last_vacuum,
       last_autovacuum,
       last_analyze,
       last_autoanalyze
FROM pg_stat_user_tables
WHERE relname IN ('bifrost_control_outbox',
                  'bifrost_outbox_consumers',
                  'bifrost_outbox_tenant_cursors',
                  'bifrost_outbox_poison');

-- Relation and index size.
SELECT relname,
       pg_total_relation_size(relid) AS total_bytes,
       pg_relation_size(relid) AS heap_bytes,
       pg_indexes_size(relid) AS index_bytes
FROM pg_catalog.pg_statio_user_tables
WHERE relname LIKE 'bifrost_outbox%'
   OR relname LIKE 'bifrost_control_outbox%';

-- Frozen XID risk.
SELECT c.relname, age(c.relfrozenxid) AS xid_age
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname LIKE 'bifrost%outbox%';

-- Long transactions that can block vacuum or delay notification delivery.
SELECT pid, state, now() - xact_start AS xact_age, query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
  AND now() - xact_start > interval '5 minutes';
```

Gateway metrics:

- `bifrost_outbox_max_id`;
- `bifrost_outbox_consumer_cursor_id{consumer}`;
- `bifrost_outbox_consumer_lag_events{consumer}`;
- `bifrost_outbox_consumer_lag_seconds{consumer}`;
- `bifrost_outbox_consumer_lease_seconds_remaining{consumer}`;
- `bifrost_outbox_listener_connected{consumer}`;
- `bifrost_outbox_listener_reconnects_total{consumer}`;
- `bifrost_outbox_poll_errors_total{consumer}`;
- `bifrost_outbox_poison_open_total{tenant,domain,risk_class}`;
- `bifrost_outbox_resnapshot_requests_total{tenant,domain,reason,status}`;
- `bifrost_outbox_compact_through_id`;
- `bifrost_outbox_compaction_blocked{reason}`;
- `bifrost_snapshot_signature_failures_total`;
- `bifrost_snapshot_revision_downgrade_rejected_total`.

Autovacuum posture:

- keep outbox events immutable and partitioned;
- update only narrow cursor/lease rows frequently;
- use low fillfactor for cursor tables;
- avoid long transactions in snapshot builders;
- prefer partition detach/drop over deletes;
- run `ANALYZE` after large resnapshot or compaction operations;
- keep poison and resnapshot tables small through repair/retention workflows.

## Multi-Pod Failure Oracles

Each oracle should run in CI where possible and in a release-candidate environment with
Aurora behavior where CI cannot reproduce it.

1. New key convergence: create one virtual key, verify it authorizes across three pods
   after all pods install a watermark at or beyond the mutation outbox ID.
2. Revocation under load: revoke a key while requests are active; every pod denies by
   the configured convergence SLO or fails closed when its freshness lease expires.
3. Notification loss: disconnect listener connections for 10 minutes; polling catches
   up without missing or reordering authority changes.
4. Aurora failover: force writer failover while consumers renew leases and drain events;
   consumers reconnect, preserve monotonic watermarks, and do not install unsigned or
   downgraded snapshots.
5. Dead consumer: kill a pod without graceful shutdown; its lease expires, it is retired,
   and compaction is no longer blocked after the retirement grace.
6. Compacted cursor: stop a pod beyond the retention floor, compact events, restart it;
   the pod detects cursor loss, installs a signed snapshot, and drains from the snapshot
   watermark.
7. Poison event: insert a malformed event in a test domain; affected tenant/domain gets
   safe quarantine, other tenants continue, alert fires, and resnapshot repairs the row.
8. Hot tenant fairness: generate many events for tenant A and one revocation for tenant B;
   tenant B's high-risk event is installed within the convergence target.
9. Mixed version: run old and new pods during schema expansion; incompatible watermarks
   are rejected by version bounds and compatible watermarks remain installable.
10. Clock skew: skew pod clocks; lease expiry and readiness decisions still use DB time.
11. Bad snapshot: publish a snapshot with invalid signature or checksum; pods reject it
    and keep last-known-good until freshness policy decides readiness/fail-closed.
12. Poison plus compaction: quarantined event pins compaction until resnapshot repair or
    explicit safe-disposition record allows compaction.
13. Long transaction: hold a long read transaction while writers publish events; metrics
    expose delayed notification/vacuum risk and polling still catches committed events.
14. Partitioned pod: block pod egress to Aurora; it serves only until freshness leases
    expire, then leaves readiness and fails closed for affected authority classes.

## Alternatives

### Polling Only

Simplest correctness model. It is acceptable if measured convergence and Aurora read cost
are within launch targets. It should remain the fallback even when notify is enabled.

Tradeoff: adds a predictable latency floor and steady Aurora reads proportional to pod
count.

### Outbox Plus LISTEN/NOTIFY

Recommended launch default if Aurora failover tests pass. It preserves the polling
repair path while reducing normal-case wakeup latency.

Tradeoff: needs dedicated listener connections, reconnect logic, and proof that RDS
Proxy/direct connection choices do not break listener behavior.

### Redis Streams Relay

PostgreSQL remains authority; a relay copies outbox rows to Redis Streams for fanout.

Tradeoff: useful only after measured Aurora fanout cost or convergence fails. Adds a
second operational surface and at-least-once relay idempotency.

### Logical Replication Or CDC

Can support high-volume downstream consumers, but row-level changes are not always
domain events and replication-slot lifecycle becomes an operations dependency.

Tradeoff: not launch default. Consider only when outbox throughput or independent
consumer count materially exceeds the simpler design.

### Gossip Or Peer Snapshot Transfer

Fast in some partitions, but unsafe as sole authority for revocation, spend, or identity
policy.

Tradeoff: possible portability adapter after launch. Kubernetes plus Aurora already
covers launch membership and authority.

### Shared Filesystem Snapshots

Useful for offline import/export or disaster bootstrap bundles. Not suitable for live
revocation authority because watcher semantics, stale mounts, and writer fencing become
the hard problem.

## Rollback And Safe Evolution

Use expand/contract migrations:

1. Create outbox, cursor, poison, resnapshot, and watermark tables with no writers.
2. Start dual-writing outbox rows from control-plane mutations while existing local
   reload behavior remains active.
3. Run consumers in shadow mode: build snapshots, verify signatures, compare decisions,
   but do not gate readiness.
4. Enable readiness on signed snapshot install for a small canary set of pods.
5. Enable all pods after failure oracles pass.
6. Only then remove old single-pod reload assumptions.

Rollback levers:

- Disable notification listeners: consumers continue polling.
- Disable consumers as authority: pods keep last-known-good snapshot and control-plane
  writes may be frozen while operators roll back.
- Revoke a bad watermark: mark `status = 'revoked'` and publish a high-risk outbox event
  forcing pods to reject it.
- Roll back to a previous snapshot: publish a `rollback` watermark signed by the
  emergency rollback key with reason, approver, previous watermark ID, compatibility
  bounds, and expiry. Pods reject ordinary revision downgrades.
- Stop compactor: safe; it increases storage/WAL pressure but does not affect inference.
- Keep additive tables during application rollback. Dropping tables is a later contract
  step only after all old binaries and watermarks are gone.

Rollback must not widen security or spend from ambiguous state. If the rollback target
would re-enable a revoked key, increase spend, or broaden MCP/tool access, it requires
the same approval and alert path as any other security/spend increase.

## Acceptance Checklist

- Authority mutation and outbox insert are atomic.
- Notifications contain no authority payload and are never required for correctness.
- Every active consumer has a lease, cursor, installed watermark, and freshness metrics.
- Dead consumers are retired and do not block compaction after the grace period.
- Poison events produce safe local disposition, alerting, and resnapshot.
- Compaction is blocked by active cursors, retention, and unresolved poison.
- Tenant/domain lag is visible and high-risk changes are prioritized.
- Snapshot watermarks are signed, version-bounded, monotonic, and rollback-aware.
- New pods without verified snapshots stay unready during Aurora impairment.
- Failure oracles cover notification loss, Aurora failover, dead consumers, poison,
  compaction/resnapshot, mixed versions, clock skew, and tenant fairness.
