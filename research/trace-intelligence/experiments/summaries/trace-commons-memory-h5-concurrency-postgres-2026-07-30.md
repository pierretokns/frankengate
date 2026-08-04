# Trace Commons memory H5 concurrency gate — local PostgreSQL

Date: 2026-07-30

Status: **mechanics passed with architecture gaps**

## Claim boundary

This is a content-free, multi-session conformance run against the disposable
`colima` lab: PostgreSQL 16.12 and pgvector 0.8.1. It is not an Aurora test and
does not establish RDS Proxy behavior, failover, replica lag, durability,
scale, memory correctness, memory utility, identity, or enterprise transfer.

The suite stored only deterministic `tc-h5c-*` fixture identities, empty
`raw_payload` objects, aggregate-free fixture labels, and fixed hashes. It
stored zero trace events, prompts, responses, file paths, tool identifiers, or
extracted memory text. Every race worker that changed protected rows used a
`NOSUPERUSER NOBYPASSRLS NOINHERIT` role that owns no protected relations.
The disposable fixture login seeded and removed fixtures, held advisory
barriers, and observed session wait states.

This is not a single rollback-only transaction like `007`: independent
sessions cannot observe uncommitted setup from a parent transaction. Failed
workers and visibility readers roll back; the promotion, withdrawal,
governance, and deletion handoffs deliberately commit so later sessions can
observe them. A `finally` teardown then deletes every fixture and independently
asserts zero rows, helper functions, roles, and worker sessions.

## Exact schedules and results

| Case | Deterministic schedule | Result |
|---|---|---|
| Failed evaluator job | A non-owner evaluator inserted stage one, stage two violated `evaluation_runs_cost_microunits_check`, and `ON_ERROR_STOP` disconnected inside the aborted transaction. | Worker returned 3; zero `tc-h5c-eval-job-*` rows survived. |
| Concurrent promotion | Barrier 85001 held A after its active insert. B attempted a second same-candidate active insert and was observed waiting on `transactionid`. A committed, then B hit `artifact_releases_one_active_candidate_idx`. | Exactly one active release; A won; B persisted nothing. |
| Withdrawal plus replacement promotion | Barrier 85002 held A after marking the current release withdrawn. C attempted promotion and was observed waiting on `transactionid`. A committed, then C committed. | A withdrawn; C is the sole active release. |
| Exposure plus withdrawal | Barrier 85003 held an app transaction after exposure insert. The releaser withdrew C and committed; the app committed afterward. | Runtime visibility was zero, but one `status=active` exposure row remained attached to a withdrawn release. |
| Epoch, READ COMMITTED | Reader saw release D, blocked at 85004, epoch 51→52 committed, reader resumed. | Visibility 1→0. |
| Epoch, REPEATABLE READ | Reader established a snapshot, blocked at 85005, epoch 51→52 committed, reader resumed. | Visibility 1→1 until transaction end. |
| Membership, READ COMMITTED | Reader saw release D, blocked at 85006, membership revoke committed, reader resumed. | Visibility 1→0. |
| Membership, REPEATABLE READ | Reader established a snapshot, blocked at 85007, membership revoke committed, reader resumed. | Visibility 1→1 until transaction end. |
| Hard deletion, READ COMMITTED | Reader saw the independent trajectory, blocked at 85008, authorized app deletion committed, reader resumed. | Visibility 1→0. |
| Hard deletion, REPEATABLE READ | Reader established a snapshot, blocked at 85009, authorized app deletion committed, reader resumed. | Visibility 1→1 until transaction end. |
| Provenance source deletion | Authorized app tried to delete a trajectory referenced by `candidate_sources`. | FK rejected the deletion and the aborted transaction preserved the source. |

The complete machine-readable receipt is
[`trace-commons-memory-h5-concurrency-postgres-2026-07-30.json`](../results/trace-commons-memory-h5-concurrency-postgres-2026-07-30.json).
The executed SQL suite SHA-256 is
`ebf1064faef1466df973eb693cd4d2ffe1f0033e04b0371f25ffdbafca619ebc`.

## Architecture gates found

1. **Withdrawal is visibility-safe but not metadata-atomic with exposure.**
   RLS hides exposures after the parent release becomes inactive, but it does
   not end or roll back a concurrently committing exposure. Promotion and
   withdrawal need a single database command/procedure that locks the release,
   changes release status, ends active exposures, and appends the lifecycle
   event in one transaction. Exposure creation must take the same lock and
   recheck active status after acquiring it.
2. **Continuous revocation cannot be promised inside REPEATABLE READ.** Epoch,
   membership, and hard-deletion checks use the transaction snapshot. The
   application contract must use one short READ COMMITTED transaction per
   request, or a revocation mechanism outside the old MVCC snapshot. Merely
   calling a `STABLE SECURITY DEFINER` function again is insufficient.
3. **The research schema lacks a persistent non-owner governance writer.** The
   test used an ephemeral non-owner role with prefix-restricted security-definer
   helpers and removed both afterward. A real design needs a narrow,
   tenant-scoped authority mutation API; it must not grant table-wide updates
   directly.
4. **Provenance deletion is retention, not deletion.** The default FK from
   `candidate_sources` rejects source deletion once a candidate depends on it.
   The product needs an explicit retention/redaction/tombstone policy rather
   than assuming hard deletion will cascade.
5. **Lifecycle event coupling is conventional.** The schema permits release
   status updates without a corresponding event and does not prove event/status
   agreement. The test actor wrote both in one transaction, but the database
   does not force every caller to do so.

## Cleanup receipt

The final cleanup and independent verification reported:

- fixture rows: 0
- temporary helper functions: 0
- temporary roles: 0
- marker: `H5C_ZERO_RESIDUE_OK`

## Reproduction

Run only against the disposable `colima` fixture:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  research/trace-intelligence/tests/run_trace_commons_memory_h5_concurrency.py \
  --timeout 30
```

The runner refuses any Kubernetes context other than `colima`, checks
PostgreSQL 16 and pgvector 0.8.1, observes each lock barrier through
`pg_stat_activity`, requires exact expected failure signatures, and invokes
cleanup plus the zero-residue assertion in `finally`.
