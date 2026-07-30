# Defog governed PostgreSQL replay conformance

## Result

The hardened Frankengate replay boundary semantically matched all 95 source
tasks that were executable under a valid policy. The 96th source task is not
valid PostgreSQL even after the single auditable brace-struct repair and is
quarantined pending manual adjudication or replacement.

This is a verifier and security-policy self-check. It is not a model factorial
and does not establish that a mined skill improves SQL generation.

| Check | Result |
|---|---:|
| Frozen cohort | 96 tasks; four database families |
| Default-policy semantic matches | 93 |
| Expected default sensitive-projection denials | 2 |
| Explicit field-entitlement semantic matches | 2/2 |
| Expected default wildcard denial | 1 |
| Source-invalid PostgreSQL tasks | 1 |
| Executable tasks matched by hardened comparator | 95/95 |
| Database families passing every security control | 4/4 |

The strict default did exactly what it should: it did not silently grade
requested phone/email output as authorized, and it rejected `SELECT *`. The two
sensitive tasks passed only in the conformance-only arm with explicit
field-level entitlements. Production authorization must supply those
entitlements; the runner must never infer them from gold SQL.

## Security boundary exercised

For every database family, the run used a constrained PostgreSQL login with
`NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, `NOBYPASSRLS`, and a
read-only transaction. The runtime required a governance subject and current
authorization-epoch reference, set transaction-local row-security and timeout
controls, and bounded result rows and bytes.

The parser and database layers independently denied:

- multiple statements;
- mutation and DDL;
- direct mutation below the parser boundary;
- system file-reading functions;
- unknown tables;
- wildcard projection; and
- governance scope without an authorization epoch.

Candidate results preserve row tuples, duplicates, nulls, numeric tolerance,
types, and order when the gold query orders. Extra columns are rejected.
Semantic correctness and security authorization are separate verdicts.

## Upstream defect found

One row in the pinned PostgreSQL CSV uses brace-struct syntax and an empty
brace group expression. SQLGlot can parse it, but naïve serialization produces
`STRUCT(...)`, which PostgreSQL does not implement. Rewriting the projection to
native `ROW(...)` still fails PostgreSQL grouping rules. The task therefore
remains in the source audit denominator but is excluded from the 95-task
executable denominator.

This also demonstrates why the stock evaluator's SQLite self-check cannot be
used as evidence that a purported PostgreSQL cohort is PostgreSQL-valid.

## Reproduce

Install the pinned environment and materialize the four disposable databases
from the pinned Defog Data checkout. Keep the source checkout and raw audit
directory outside Git. Then run:

```sh
DEFOG_SOURCE_ROOT=/private/path/defog-sql-eval \
DEFOG_REPLAY_DSN_TEMPLATE='host=127.0.0.1 port=55432 user=... dbname=fg_defog_{database}' \
DEFOG_RAW_AUDIT_DIR=/private/path/defog-raw-audit \
uv run make defog-sql-conformance
```

The committed aggregate contains only source hashes, counts, policy outcomes,
and result-receipt hashes. Candidate SQL and per-tool records remain in the
external raw audit directory.

## Next experiment

Freeze 95 executable tasks into four rotating schema-family folds, then compare:

1. no mined evidence;
2. unrelated SQL-skill placebo;
3. raw retrieved history;
4. concise schema-navigation skill;
5. business-rule/metric skill;
6. failure-to-repair skill;
7. verified exemplars; and
8. the preregistered composition.

Capture every schema inspection, SQL proposal, database error, result hash,
revision, refusal, skill exposure, authority epoch, latency, token usage, and
cost. The next result must report paired semantic lift, regressions, security
violations, and abstention—not just execution accuracy.
