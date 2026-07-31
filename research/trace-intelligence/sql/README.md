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

kubectl exec -i -n frankengate-test postgres-0 -- \
  psql -U frankengate -d frankengate -v ON_ERROR_STOP=1 \
  < research/trace-intelligence/sql/005_skill_release_lifecycle.sql

kubectl exec -i -n frankengate-test postgres-0 -- \
  psql -U frankengate -d frankengate -v ON_ERROR_STOP=1 \
  < research/trace-intelligence/sql/006_skill_release_assertions.sql

kubectl exec -i -n frankengate-test postgres-0 -- \
  psql -U frankengate -d frankengate -v ON_ERROR_STOP=1 \
  < research/trace-intelligence/sql/007_trace_commons_memory_h5_assertions.sql
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

`005_skill_release_lifecycle.sql` adds separate proposer, evaluator, releaser,
and runtime roles plus governed candidate provenance, frozen replay manifests,
independent outcomes, signed releases, exposure, influence, and release-event
records. `006_skill_release_assertions.sql` executes 18 rollback-only
conformance checks through the non-owner roles. It proves hidden-test
separation, release/security vetoes, no scope broadening, immutable signed
fields, authorized influence tracking, withdrawal, and stale-epoch denial.
It does not prove that a mined skill improves a real task, and it does not
emulate Aurora operations, failure, concurrency, or scale.

`007_trace_commons_memory_h5_assertions.sql` is the rollback-only PostgreSQL
phase for the content-free Trace Commons memory-composition result. It uses
synthetic authority values and aggregate counters only; raw traces, events,
prompts, responses, paths, tool identifiers, and extracted memory text remain
outside PostgreSQL. Its 20 invariant checks and six expected-denial checks
prove team-scoped RLS denial, proposer/evaluator separation, gated release,
authorized exposure and influence recording, and rollback visibility for
source result
`3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5`.
It does not establish memory correctness, utility, failed-job atomicity, skill
improvement, identity, continuous validity, Aurora operations, or enterprise
transfer.

`009_skill_release_atomic_lifecycle.sql` adds the narrow procedure contract
found necessary by H5: exposure creation and release transitions lock the
release row, re-check authorization and active status after the lock, and
couple release status, exposure termination, and lifecycle-event insertion.
`010_skill_release_atomic_lifecycle_assertions.sql` is rollback-only. The
multi-session race and cleanup are driven by
`tests/run_skill_release_atomic_lifecycle_race.py` using
`011_skill_release_atomic_lifecycle_race.sql`.

`012_finance_retrieval_768.sql` is a separate disposable FinanceBench gate. It
keeps the native 768-dimensional finance embedding, creates an HNSW index, and
uses a forced-RLS policy whose authority epoch, tenant, subject, purpose, and
classification checks happen before vector ranking. The paired
`finance_governed_retrieval_replay.py` runner also checks soft deletion and
transaction rollback. It is local PostgreSQL evidence only; it is not an
Aurora availability, failover, or production migration.
