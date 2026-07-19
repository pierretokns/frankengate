# Upstream v2.0 prerelease adoption gate

The prerelease label is not treated as proof that a feature is production
ready. FrankenGate records a decision only when a production caller, route,
and focused end-to-end test exist.

| Upstream delta | Current decision | Required evidence before adoption |
| --- | --- | --- |
| ChatGPT passthrough (`d7d0dc8b7`) | Adapted in the router/provider passthrough path | Explicit safe-header and auth policy plus unary, streaming, and cancellation tests. |
| User-Agent/app tracking (`5510b7eb0`, `68f55c50d`) | Deferred | PII retention/redaction, bounded-cardinality/index-cost, authorization, migration, and rollback proof. |
| Mapping APIs | Deferred pending route/production caller audit | Registered CRUD/filter routes and authorization tests. |
| Edge-agent MCP log columns (`55269535d`) | Deferred | Real ingestion and control-plane consumers; otherwise reject from advertised surfaces. |
| Edge fallback surfaces (`b71aadbb2`) | Deferred | Production caller and failure-mode tests. |

The release scan must verify imports and invocation from production entry points;
type definitions or UI-only pages do not satisfy reachability.
