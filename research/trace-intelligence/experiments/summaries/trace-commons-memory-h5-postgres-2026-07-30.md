# Trace Commons memory H5 PostgreSQL conformance

**Run date:** 2026-07-30

**Status:** bounded real-component pass

## Result

The rollback-only suite bound the audited full-cohort result
`3084635035e330948861c763c015cf4f6394361f7fb3960b29928fb70a1a2af5`
to a content-free synthetic procedure: require contextual identity and reject
basename-only latest memory. It ran against PostgreSQL 16.12 with pgvector
0.8.1 in the disposable local Kubernetes fixture.

All 26 assertions passed:

- 20 count and invariant checks;
- 6 expected-denial checks;
- forced RLS on all ten protected lifecycle tables;
- safe non-owner runtime roles;
- fail-closed missing, wrong-tenant, wrong-team, and stale-epoch authority;
- proposer/evaluator separation and hidden-test write denial;
- no release before independent selection and hidden gates;
- authorized release exposure and influence only; and
- immediate release and exposure invisibility after rollback status.

The transaction ended with `ROLLBACK`. A separate residue query found zero
fixture rows in trajectories, candidates, releases, exposures, evaluations,
and replay manifests.

## Reproduce

Install the research schema and lifecycle DDL once in a clean disposable
database, then run:

```sh
kubectl exec -i -n frankengate-test postgres-0 -- \
  psql -U frankengate -d frankengate -v ON_ERROR_STOP=1 \
  < research/trace-intelligence/sql/007_trace_commons_memory_h5_assertions.sql
```

The checked-in local fixture now pins the same
`docker.io/pgvector/pgvector:0.8.1-pg16` manifest digest used by this run.

## Claim boundary

The run proves bounded PostgreSQL role, forced-RLS, release, exposure,
influence, withdrawal, and transaction-rollback mechanics for a content-free
aggregate. It does not prove Aurora failover or PITR, concurrency behavior,
memory quality, failed-job atomicity, skill improvement, human identity, or
enterprise transfer. The schema still treats `content_sha256` as a
caller-supplied artifact identity; the database does not recompute it from
`content_text`.
