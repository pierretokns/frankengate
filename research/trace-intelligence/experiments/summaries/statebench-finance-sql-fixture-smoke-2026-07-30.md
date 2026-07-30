# StateBench finance SQL fixture smoke

The pinned `finance-retrieval-sql-v0` fixture passed all 46 internal consistency
checks. Four tasks execute gold SQL, three declare refusal controls, and the
remaining 39 are retrieval or control contracts.

This is a useful adapter and safety baseline, not a skill-learning corpus. The
runner used in-memory SQLite, so it proves neither PostgreSQL roles/RLS nor
Aurora behavior. Frankengate should expand the executable SQL stratum to 60–120
audited tasks grouped by schema family before comparing learned skills.

The next run must use real PostgreSQL with a non-owner `NOSUPERUSER
NOBYPASSRLS` role, read-only transactions, statement and row limits, an
`EXPLAIN` cost gate, first-class tool-call traces, and a zero-tolerance
authorization-leakage score.
