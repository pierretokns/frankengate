# Validation-carrying artifact capsule reuse — 2026-08-02

This bounded lab turns a parameterized SQL procedure into a versioned capsule
and attempts reuse under valid and invalid runtime contexts. The capsule binds
parameters, records a schema fingerprint, authority scope, authorization epoch,
result columns/types, expiry, and a content hash.

| Case | Result |
| --- | --- |
| valid scope/epoch/schema/parameters | accepted |
| stale authorization epoch | denied |
| wrong authority scope | denied |
| expired capsule | denied |
| parameter contract mismatch | denied |
| schema drift | denied |
| SQL-injection-shaped parameter | bound as a value; never interpreted as SQL |

All five invalid-context cases failed closed. This proves capsule/reuse
mechanics in an in-memory SQLite fixture only. It does not prove PostgreSQL or
Aurora compatibility, semantic result equivalence across parameter values,
artifact quality, or user benefit. The production version still needs the
existing governed PostgreSQL executor, dialect/schema migration rules, result
equivalence policy, source-trace provenance, and independent replay gates.

