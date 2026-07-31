# PostgreSQL/Aurora architecture gate (2026-07-31)

The local evidence supports one governed PostgreSQL authority for the current
Frankengate scope. Wisp policy/query, H5 forced-RLS lifecycle, concurrency
mechanics, and E2 retrieval results all keep authorization ahead of ranking and
show zero unauthorized candidates in their disposable fixtures.

The H5 concurrency run also found real design edges: withdrawal is not
metadata-atomic with a concurrently committing exposure; continuous revocation
cannot be promised inside a `REPEATABLE READ` snapshot; provenance FKs provide
retention rather than hard deletion; lifecycle events are not database-enforced
alongside status changes; and the tested non-owner governance writer was
ephemeral. These are implementation gates, not reasons to add another database.

No Aurora claim is made. Writer/reader failover, RDS Proxy, replica lag, PITR,
partitioning at hundreds of gigabytes, and managed extension compatibility
remain untested. The current host's `colima` Kubernetes API was unreachable
under the sandbox, so this checkpoint relies only on previously recorded local
receipts and does not fabricate a new database run.
