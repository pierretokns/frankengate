# Authorized internal trace fidelity: OSS code audit

Status: implementation plan
Date: 2026-07-30
Tracking: [GitHub #116](https://github.com/pierretokns/frankengate/issues/116),
bead `bif-kyy.16.2.1`

## Issue details

Frankengate must retain useful prompt, response, tool, and trace content—including
PII—for the authorized user and internal administrators. It must not disclose that
content to third parties, unrelated scopes, public exports, or lower-privilege
audiences merely because it was logged.

The reported failure is narrower than ordinary content logging. When a guardrail
replaces PII with placeholders, OSS carries the phase-scoped placeholder-to-original
map only in memory. The database column, API response type, and UI reveal control
exist, but persistence and resolution are delegated to an absent Enterprise wrapper.
The result is irreversible evidence loss for internal administrators.

Expected behavior:

- same-scope internal log detail can reconstruct a transformed input or output;
- the owner can reveal their own row, a team member only their granted scope, and an
  administrator only an explicitly granted scope or reason-bound audited override;
- backend authorization and RLS remain authoritative; the permissive OSS UI fallback
  is not evidence of permission;
- credentials and authentication headers remain excluded;
- list/error/telemetry surfaces never receive the mapping; an explicitly authorized,
  encrypted same-scope internal export may receive resolved content but never the
  mapping object itself, while third-party/public exports receive transformed content.

## Classification

- Type: architecture defect and OSS feature completion.
- Severity: P0 because lossy capture undermines incident review, eval creation,
  memory/skill research, and user-history usefulness.
- Affected areas: logging plugin, logstore, HTTP log-detail handler, UI log detail,
  authorization/RLS tests, migration compatibility, documentation.
- Change class: non-breaking API completion for ordinary callers; reveal behavior is
  newly available only to already-authorized readers.

## Codebase analysis

| File | Current behavior | Required change |
|---|---|---|
| `plugins/logging/main.go` | Copies `RedactionData` from request context into a transient log field. | Prepare a versioned durable reversible-mapping envelope before the async write. |
| `plugins/logging/writer.go` | Persists batches without converting the transient mapping. | Serialize only placeholder-to-original maps, encrypt when configured, clear transient data, and keep base-log writes available on preparation failure. |
| `framework/logstore/tables.go` | Declares `RedactionData` as `gorm:"-"`; comments say an Enterprise wrapper writes `RedactionMapping`. | Make the durable field an OSS contract and document its lifecycle. |
| `framework/logstore/migrations.go` | Already creates the `redaction_mapping` column. | Retain migration compatibility; add envelope-version/read tests rather than a new column unless measurement requires one. |
| `transports/bifrost-http/handlers/logging.go` | Calls an optional Enterprise-only resolver before returning log detail; audit export explicitly strips all content and mappings. | Resolve the OSS envelope after row authorization; keep resolution absent from list/export paths and fail reveal closed without failing the base detail response. |
| `transports/bifrost-http/server/server.go` | Wires a resolver only when callbacks implement an Enterprise extension interface. | Remove that product-coupled seam after OSS resolution exists. |
| `ui/app/workspace/logs/sheets/logDetailView.tsx` | Already applies input and output mappings separately behind a reveal toggle. | Preserve the phase separation; add authorized/denied/malformed response tests. |
| `ui/app/_fallbacks/enterprise/lib/contexts/rbacContext.tsx` | OSS fallback allows every operation, including Reveal. | Replace this fallback dependency and require a backend `logs:reveal` decision before enabling reveal; never treat the dashboard route or UI state as administrator proof. |

### Root cause and hard edges

The upstream abstraction split storage and reveal mechanics across OSS and a private
wrapper. Frankengate removed that product boundary without completing ownership of the
mapping lifecycle. Merely retaining raw pre-transform text elsewhere would create a
second untracked copy; the smaller solution is to persist the existing phase-scoped
mapping ciphertext in the same log row and deletion lifecycle. It remains logically
separate through a versioned envelope/key, omission from normal projections and
indexes, and a dedicated scoped reveal operation.

At-rest encryption alone is not authorization. The row must first pass the normal
user/team/admin scope predicate. PostgreSQL documents that table owners normally bypass
RLS and that `BYPASSRLS`/superuser roles always bypass it; the application role must
therefore remain `NOSUPERUSER NOBYPASSRLS`, with `FORCE ROW LEVEL SECURITY` in the
governed profile. [PostgreSQL row-security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

The existing encryption package uses AES-GCM. Go documents `cipher.NewGCM` as an AEAD
with the standard nonce length; reuse this implementation and a versioned envelope
instead of introducing a second cipher. [Go `crypto/cipher` documentation](https://pkg.go.dev/crypto/cipher#NewGCM)

OpenTelemetry's own sensitive-data guidance places hashing, deletion, and redaction in
collector/export processing. That supports a destination transform on third-party
export while retaining a separately governed internal source.
[OpenTelemetry sensitive-data guidance](https://opentelemetry.io/docs/security/handling-sensitive-data/)

## Impact analysis

| Change | Benefit | Risk | Mitigation |
|---|---|---|---|
| Persist reversible map | Restores internally useful evidence after a guardrail transform. | Mapping contains PII and increases row size. | Same-row lifecycle, bounded entry/count/bytes, encryption, retention, audit, and no list projection. |
| OSS detail resolver | Makes the existing UI reveal control functional. | An authorization mistake reveals content. | Resolve only after scoped row fetch; backend permission test; no caller-supplied subject/scope. |
| Remove private-wrapper seam | Eliminates a misleading missing dependency. | Downstream callback implementation conflict. | Preserve legacy envelope reads and release-note the resolver ownership change. |
| Destination transforms | Prevents external disclosure without degrading internal analysis. | Sink omission creates leakage. | Destination registry, deny-by-default external egress, exact outbound rescan, conformance canaries. |

The mapping object must not enter websocket list updates, aggregate queries,
object-store previews, exports, connector callbacks, error messages, traces, or model
evidence packs. Resolved content may enter an explicitly authorized same-scope internal
export or analysis job after its own purpose, encryption, retention, and audit gate; a
third-party/public destination receives a transformed copy. A wrong/missing key,
corrupt envelope, or unknown version returns the base redacted log and an auditable
reveal failure; it never returns guessed plaintext and never fails the full log-detail
request.

## Implementation plan

1. Define a bounded, versioned mapping envelope containing phase-scoped reversible
   mappings, source log ID/digest binding, encryption disposition, and no literal
   raw-to-placeholder duplicate.
2. Convert transient `RedactionData.ReversibleMappings` immediately before storage,
   using the existing `framework/encrypt` key when enabled. Clear the transient object
   before callbacks.
3. Decode after the already-scoped log-detail fetch and only when the caller has the
   OSS `logs:reveal` permission. Support owner scope, granted team scope, and a
   reason-bound audited administrator override. Keep list/session/export endpoints
   mapping-object-free.
4. Remove Enterprise-only resolver comments/interfaces after compatibility tests pass.
5. Preserve the current UI phase-specific replacement logic and add explicit failure
   states without placing original values in client logs or telemetry.
6. Treat third-party connectors and OTEL exporters as independent destinations that
   require their own transformed copy/receipt; never forward the reversible map.

## Test plan

### Existing tests to extend

- `plugins/logging/redaction_test.go`: durable envelope preparation, input/output phase
  isolation, owned-copy behavior, content-disabled behavior.
- `plugins/logging/sanitize_test.go`: mapping cannot leak through error serialization.
- `transports/bifrost-http/handlers/logging_test.go`: detail reveal success/failure and
  audit-export non-disclosure.
- `framework/logstore` PostgreSQL tests: same-row insert/delete/retention behavior and
  RLS visibility.
- `tests/e2e/features/logs`: reveal toggle, phase separation, denied caller, and no value
  in list/network/error output.

### New cases

1. Encryption enabled: round trip succeeds for the owner, an authorized team reader,
   and a reason-bound administrator.
2. A versioned plaintext envelope is permitted only in an explicit single-user
   development profile; multi-user startup rejects it.
3. Wrong/missing key, malformed ciphertext, malformed JSON, unknown version: reveal
   fails closed while base detail succeeds.
4. Legacy encrypted/plain rows remain readable under their documented configuration.
5. Batch insert failure and individual fallback do not duplicate or lose the mapping.
6. User A, unrelated team, deleted membership, stale authorization epoch, and
   `BYPASSRLS`-free application role cannot reveal User B's mapping.
7. Input mapping cannot affect output content and vice versa.
8. List, session list, websocket update, connector payload, OTEL export, error
   serialization, and deletion receipt contain no mapping or original value. A
   third-party/public export is transformed; an authorized encrypted same-scope export
   may contain resolved content but never the mapping object.
9. Oversized mapping follows an explicit bounded policy and cannot exhaust the writer.
10. Deleting the row deletes the mapping; no detached re-identification object remains.

No provider-level LLM or MCP scenario is needed because this change does not alter
provider conversion or tool execution. The relevant gates are logging-plugin unit/race
tests, real PostgreSQL RLS tests, HTTP handler tests, and logs E2E.

## Recommendation

Proceed with this small OSS completion before building broader PII detectors. It fixes
the actual internal evidence-loss path and preserves the current smallest-system
architecture: one authoritative log row, one scoped detail read, one existing
encryption facility, and destination-specific transforms only when content crosses a
boundary.
