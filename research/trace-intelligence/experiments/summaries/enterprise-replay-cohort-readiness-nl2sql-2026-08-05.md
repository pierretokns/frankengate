# Enterprise replay cohort readiness audit (2026-08-05)

The governed changed-system protocol was run against the 42-case public Defog
alias cohort. It is useful for retrieval diagnostics but is not eligible for a
causal enterprise replay:

- 42 records, zero principal/team/project/system identity fields;
- no two-annotator labels or adjudication;
- no changed-environment identifiers;
- no independent outcome field;
- below the minimum 100-target / 50-hard-negative / 25-NIL-or-unclear gate.

`ready_for_causal_replay` is therefore **false**. This is a positive audit
result because it prevents a public gold-SQL proxy from being reported as
enterprise semantic or skill evidence. The content-free receipt and verifier
are:

`experiments/results/enterprise-replay-cohort-readiness-nl2sql-2026-08-05.json`

The next admitted cohort must add stable pseudonymous principal/team/project/
system IDs, two independent semantic labels, changed-system fixtures, and
independent outcome receipts before any cross-user or artifact-utility claim.
