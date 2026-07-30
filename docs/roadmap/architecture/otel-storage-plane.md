# OTEL storage plane contract (v1)

This is the storage boundary for traces, tool calls, model I/O metadata, and
replay references. It is deliberately outside the inference request path.

## Placement

| Data | System | Authority | Default retention |
|---|---|---|---|
| searchable scalar metadata | Aurora PostgreSQL | row + tenant RLS | 90 days |
| bounded full-fidelity or transformed compact payload (per policy and destination) | Aurora `jsonb` | row + tenant/user/team RLS | policy-selected |
| raw/high-volume payload or media | S3, SSE-KMS | immutable object manifest in Aurora | policy-selected |
| embeddings/derived index | optional pgvector or governed Frankensearch | source record remains Aurora | rebuildable |
| delivery state | Aurora outbox + consumer lease | source revision/cursor | until acknowledged + compaction |

Every record carries `tenant_id`, `principal_id`, `team_id`, `classification`,
`purpose`, `policy_revision`, `schema_version`, `producer_version`,
`source_revision`, `content_disposition`, optional `transform_profile`, and
`deletion_epoch`. Payloads are content-addressed by SHA-256; the digest is not
authorization.

## Ingestion contract

1. The internal OTEL/storage boundary creates a bounded envelope from an allowlisted
   trace snapshot. Credentials and authentication headers are excluded; prompt/output
   content and PII may be retained when internal content policy permits them.
2. Classification and scope binding run before the envelope enters the outbox.
   Transformation runs only for a destination that requires it. A failed required
   transform fails that disclosure closed to metadata-only or drop while preserving
   the authorized internal source.
3. The envelope is written transactionally with an idempotency key. The
   outbox contains only bounded metadata and a payload reference, never an
   unbounded stream or raw secret.
4. A storage worker uploads S3 objects first, then commits the immutable
   manifest/status transition. Retries are idempotent; orphan objects are
   garbage-collected only after the manifest grace period.

## Read, replay, and deletion

Reads require the same tenant/purpose authorization envelope as vector
retrieval. User scope is the default; team scope requires an explicit team
grant; administrators receive an auditable override, never an implicit bypass.

Replay returns an immutable snapshot at the caller's authorized fidelity plus
provider/model/config revision references. A lower-privilege or external destination
receives its transformed projection. Replay never silently rehydrates current
credentials, keys, MCP grants, or routing policy. A replay job must re-authorize at
execution time and records the policy revision used for both selection and execution.

Deletion advances the tenant deletion epoch, tombstones the Aurora row, emits
an outbox tombstone, and schedules S3/index deletion. Search indexes are
rebuildable projections and must treat a missing or stale tombstone as a deny,
not as permission to return a candidate.

## Required metrics and failure behavior

Expose counters/histograms for envelope accepted/rejected, transform failure,
outbox depth/age, upload retry, orphan cleanup, replay denied, replay latency,
and deletion lag. S3 or index outages must not block inference; they degrade
analytics to a bounded durable outbox and alert operators. Aurora authority or
RLS failures deny the affected read/write rather than falling back to an
unscoped store.

This contract is the gate for implementing the durable OTEL adapter and the
dashboard/replay consumers; it does not claim those adapters are complete.
