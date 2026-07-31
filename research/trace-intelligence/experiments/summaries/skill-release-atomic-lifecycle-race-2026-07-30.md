# Atomic release lifecycle race

**Status:** passed on disposable PostgreSQL 16.12 / pgvector 0.8.1.

The H5 race first showed that direct exposure insertion and release withdrawal
could leave an `active` exposure attached to a withdrawn release. The new
procedure contract takes the same row lock for both operations, rechecks the
release status after locking, updates active exposures, and appends the lifecycle
event in the same transaction.

The deterministic two-session schedule was:

1. Exposure creation locked the active release and waited at an advisory barrier.
2. Withdrawal waited on the release row lock.
3. Exposure committed.
4. Withdrawal acquired the lock, rechecked state, ended the exposure, and wrote
   one `withdrawn` event.

Observed results: zero active exposures after withdrawal, exactly one lifecycle
event, and zero fixture residue. The rollback-only procedure assertions also
passed, including rejection of a new exposure after withdrawal.

This closes the local exposure/status/event race for the procedure contract. It
does not prove Aurora or RDS Proxy behavior, continuous revocation inside
`REPEATABLE READ`, failover, PITR, scale, or production migration enforcement.

Machine-readable receipt: [`skill-release-atomic-lifecycle-race-2026-07-30.json`](../results/skill-release-atomic-lifecycle-race-2026-07-30.json).
