# Retrieval backend parity (bounded)

Pinned cohort: 145 documents / 99 queries.

Only offline ranking and the local forced-RLS PostgreSQL run have same-corpus evidence. CASS was capability-probed but its indexed corpus is not the pinned cohort. Frankensearch, pg_textsearch, pgContext, TurboVec, and Turbopuffer are explicit nulls, not zero scores.

The PostgreSQL receipt carries the existing authorization/deletion oracles. It does not establish Aurora scale, selective-scope concurrency, or managed-service behavior.

Architecture gate: retain PostgreSQL as policy/evidence authority; do not replace it with an unrun backend. A backend promotion requires the same corpus, exact-ID and semantic labels, pre-ranking authorization, deletion closure, latency, and cost receipts.

Result SHA256: `5d82aadf62eb6da22482cacea8641513c5717d7eaca7b5fbae1213175ffa9136`
