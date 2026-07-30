# NL2SQL PostgreSQL role and snapshot audit

**Run date:** 2026-07-30

**Status:** bounded real-component pass
**Decision:** retain the distinct candidate/evaluator PostgreSQL design, but
do not count this as the complete non-reexecution or same-profile isolation
gate.

## Result

The audit ran against the existing test-only local Aurora-like PostgreSQL
stack:

- PostgreSQL `16.12` on the local Colima Kubernetes node;
- the pinned `pgvector/pgvector:0.8.1-pg16` image used by the test stateful
  set;
- one external three-task/four-row fixture;
- a unique disposable schema;
- unique `NOLOGIN`, `NOSUPERUSER`, `NOINHERIT`, and `NOBYPASSRLS` candidate
  and evaluator roles; and
- distinct `frankengate_nl2sql_candidate_v1` and
  `frankengate_nl2sql_evaluator_v1` application names.

The content-minimized aggregate reports:

| Check | Result |
| --- | ---: |
| Candidate executions | 3 |
| Evaluator-only gold executions | 3 |
| Candidate successes | 3/3 |
| Gold successes | 3/3 |
| Deliberately expected exact matches | 2/3 |
| Candidate/evaluator role identity | pass/pass |
| Candidate/evaluator write denial | pass/pass |
| Database snapshot unchanged | pass |
| Fixture definition unchanged | pass |
| Transient role/schema cleanup | pass |

The third candidate was deliberately wrong, so `2/3` exact matches confirms
that the comparison path did not merely return success for every executable
query.

## Correction made before the run

The first implementation hashed only the external experiment-definition file.
That did not satisfy the declared database-drift gate. The reviewed adapter now
hashes both the authorized relation schemas and their row multisets before the
first task, before candidate execution, between candidate and gold, after
gold, and after the final task.

A focused adversarial test mutates the database snapshot after the candidate.
The runner marks the episode `infrastructure_invalid` and refuses to execute
gold. The real run's database snapshot remained
`7697f54272ce4149957373ed9a79354c6e16b562e059707ee5b60204f0ee1552`.

The raw audit is created exclusively with mode `0600`, refuses an existing
path, and remains outside Git. It contains the SQL, task IDs, role names,
application names, and returned rows needed for authorized audit. The committed
aggregate contains none of those values.

## What this proves

- PostgreSQL 16 can support separate least-privilege candidate and evaluator
  identities without introducing another database.
- Both roles can be restricted to `SELECT` on the authorized fixture and
  denied writes.
- The coordinator sends candidate and gold SQL through distinct lane
  connections, records three calls per lane, and cleans every transient role
  and schema.
- Actual database-content drift between candidate and gold is now a fail-closed
  infrastructure outcome rather than a semantic verdict.

## What this does not prove

- The candidate and gold SQL still coexist in the coordinator process. The
  resolver/evaluator process split must remove that co-residency.
- The execution counts are enforced and recorded by the research coordinator,
  not independently reconstructed from PostgreSQL server audit rows. The
  same-profile gate still needs a server-side or cryptographically signed
  broker receipt tied to the database backend identity.
- Read-only transactions plus role grants are not a hostile SQL sandbox.
  Unsafe preinstalled `PUBLIC` or `SECURITY DEFINER` functions require a
  separate catalog allowlist/revocation audit.
- The snapshot algorithm materializes a bounded disposable fixture. It is not
  suitable for hashing hundreds of gigabytes or proving Aurora replica/failover
  consistency.
- Exact result equality is not semantic SQL correctness.
- This tests one local PostgreSQL 16 instance, not Aurora failover, PITR,
  failover identity, or RLS under concurrent tenant load.

## Gate accounting

This result upgrades the distinct-role and database-drift parts of gates 19
and 23 from design-only to real PostgreSQL component evidence. Gate 19 remains
partial until candidate execution count is independently bound to the broker,
attempt blob, submission, evaluator receipt, and server identity. Gate 23
still needs the same mutation test inside the final OCI experiment profile.

P1 and hidden therefore remain sealed.

## Reproduce

The runner requires an explicit PostgreSQL 16 operator DSN, an external
content-pinned fixture, and an external raw-audit path:

```sh
python3 nl2sql_postgres_role_audit.py \
  --dsn "$FRANKENGATE_NL2SQL_PG16_DSN" \
  --fixture-json /private/path/nl2sql-role-audit-fixture.json \
  --fixture-sha256 <64-lowercase-hex> \
  --raw-audit-jsonl /private/path/raw/nl2sql-role-audit.jsonl \
  --output-json experiments/results/nl2sql-postgres-role-audit-2026-07-30.json
```

The operator must be able to create roles and schemas, grant membership and
table access, use `SET ROLE`, and remove the disposable objects. Production
credentials must never be placed on a command line or committed.
