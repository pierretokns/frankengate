# A2A Offline Recovery Gates

These gates are deterministic Day-2 conformance checks for the A2A Agent Card
and broker recovery surface. They are intentionally offline: no DNS, no remote
Agent Card fetches, no provider calls, and no paid inference.

Run:

```bash
python3 tests/conformance/a2a/validatefixtures.py
```

The validator now executes the existing fixture/provenance checks plus
`tests/conformance/a2a/recoverychecks.py`. The recovery harness monkey-patches
socket creation during checks so accidental network access fails the run.

## Gates

| Gate | Deterministic assertion |
| --- | --- |
| Canonical card round trips | Decode/encode keeps canonical JSON and digest stable; canonical card admission succeeds. |
| Malformed and oversized cards | Invalid JSON, schema-minimal bad cards, and cards over 64 KiB are denied before admission. |
| SSRF denial | Unsafe schemes, loopback, private, link-local metadata, local hostnames, file URLs, and unapproved hosts are denied with zero provider attempts. |
| Trust and quarantine | Unapproved publisher, changed approved-card digest, and missing security requirements quarantine the card instead of silently trusting it. |
| Admission | Tenant, protocol binding, and skill denials happen before any provider attempt. |
| Broker terminal transitions | Valid submitted-to-working transition is allowed; terminal state resurrection is denied. |
| Retry limits | Transient failures retry only up to the bounded limit, then end in a failed terminal state and reject further retries. |
| Duplicate events | Exact duplicate stream events are idempotent and do not duplicate artifact side effects. |
| Conflicting or out-of-order events | Conflicting duplicate IDs, skipped event IDs, and events after terminal state are quarantined before new side effects. |
| Stale cards | Fresh cards admit; cards older than the fixed TTL deny new admission. |

These tests are the deterministic recovery contract for the live A2A broker,
Agent Card admission, inbound task store, streaming journal, and push outbox
seams. Outbound task lifecycle delivery to the OTEL observer is separately
covered by the runtime observer test and bounded metric-label test. They
complement—not replace—the Go unit/race matrix and the external
official SDK/TCK run. They do not claim that every optional TCK scenario (for
example, generic file/data artifacts or native gRPC) is implemented.

The current release evidence is six fixture checks and 30 recovery checks,
with the framework A2A/model-card packages, inbound handler, outbound broker,
push runtime, executor-result serialization, live subscription, outbound task
observer/OTEL metrics, and streaming paths covered by Go tests and race tests.
The external official TCK/SDK run is
tracked separately because its card-schema and error-classification checks
have documented upstream discrepancies and its long-lived fixture suite
reuses task IDs across tests.
