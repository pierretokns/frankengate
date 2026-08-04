# Vector retrieval backend decision

Status: design gate (2026-07-20)

## Decision boundary

The gateway's authorization envelope is authoritative for every retrieval
candidate. A vector or lexical index is an untrusted candidate generator; it
must never decide visibility. Candidate IDs are intersected with an
authorization snapshot before ranking, snippets, caches, replay, telemetry, or
learning sinks are allowed to observe them.

## Initial launch shape

Use Aurora PostgreSQL as the policy/evidence authority and the first durable
retrieval backend. Keep embeddings, classification, tenant, principal, team,
policy epoch, deletion epoch, and embedding revision in ordinary relational
columns. Enable pgvector only behind an explicit capability flag and retain a
lexical fallback for deployments that do not install the extension. PostgreSQL
RLS is defense in depth, not a substitute for application-side candidate
intersection: the same authorization predicate must be applied to every query
path and cache key.

Frankensearch is an optional, separately deployed index/query worker. It may
receive immutable, classified documents only when it runs inside the same
governed scope and enforces an equivalent authorization snapshot; otherwise it
receives a destination-transformed copy plus authorized record identifiers. Its
results are rechecked against PostgreSQL before use. It is not a required
dependency of the inference gateway and is disabled by default in Helm.

## Why not make Redis or Qdrant authoritative

Redis is useful for bounded ephemeral caches but is not acceptable as the sole
policy store. Qdrant and other external vector stores can improve recall or
scale, but their filter semantics, snapshot freshness, and tenant/RLS behavior
must be proven with live-service tests before adoption. Until then, adding one
would create a second authorization source and a stale-policy failure mode.

## Required adapter contract

An adapter must accept `(tenant, principal, purpose, policy_epoch,
embedding_revision, query)` and return only opaque record IDs plus scores. It
must reject stale policy epochs, cap candidate count and query cost, expose
timeouts/retries, and attach index revision and source digest to the result.
The caller performs the authoritative PostgreSQL intersection and records the
decision receipt. No adapter may return raw content.

## Verification gates

Before enabling pgvector or Frankensearch in a release:

1. Migration and RLS tests prove cross-tenant and post-revocation exclusion.
2. Live-service tests prove timeout, reconnect, stale-epoch, deletion, and
   duplicate-index behavior.
3. Differential fixtures compare lexical, pgvector, and optional Frankensearch
   results after authorization filtering.
4. Load tests measure p50/p95 latency and database connection reservations
   while inference is at its declared SLO.
5. Licensing, provenance, SBOM, and pinned model/index versions are recorded.

Until these gates pass, the feature remains an opt-in analytics/control-plane
capability and cannot run in gateway request workers.
