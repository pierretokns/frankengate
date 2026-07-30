# Local PostgreSQL trace-intelligence experiment

These scripts extend the existing disposable PostgreSQL 16 + pgvector 0.8.1
Kubernetes fixture. They are not production migrations and do not claim to emulate
Aurora failover, RDS Proxy pinning, reader lag, or AWS control-plane behavior.

Apply and verify:

```sh
kubectl exec -i -n frankengate-test postgres-0 -- \
  psql -U frankengate -d frankengate -v ON_ERROR_STOP=1 \
  < research/trace-intelligence/sql/001_trace_research.sql

kubectl exec -i -n frankengate-test postgres-0 -- \
  psql -U frankengate -d frankengate -v ON_ERROR_STOP=1 \
  < research/trace-intelligence/sql/002_rls_fixture.sql

kubectl exec -i -n frankengate-test postgres-0 -- \
  psql -U frankengate -d frankengate -v ON_ERROR_STOP=1 \
  < research/trace-intelligence/sql/003_rls_assertions.sql

kubectl exec -i -n frankengate-test postgres-0 -- \
  psql -U frankengate -d frankengate -v ON_ERROR_STOP=1 \
  < research/trace-intelligence/sql/004_e2_authorized_retrieval.sql
```

The assertions execute all protected queries as `trace_research_app`, a
`NOSUPERUSER NOBYPASSRLS` role that does not own the tables. They prove:

- private, team, tenant, classification, and purpose boundaries;
- missing or stale authorization epochs fail closed;
- full-text and vector candidates are authorization-filtered before ranking;
- derived artifacts cannot reveal an unauthorized source trajectory.

The fixture uses tiny eight-dimensional deterministic vectors only to test query and
authorization composition. It says nothing about embedding quality.

`004_e2_authorized_retrieval.sql` adds a separate 1024-dimensional, forced-RLS
candidate table for the pinned Qwen E2 experiment. Its synthetic conformance rows
are transaction-scoped and rolled back. It proves exact-identifier, FTS, optional
trigram, exact-vector, and optional HNSW retrieval compose with the same authority
boundary; missing, wrong, or stale authority returns zero candidates; and withdrawn
or soft-deleted documents disappear before ranking. It still does not load raw
public or enterprise traces.
