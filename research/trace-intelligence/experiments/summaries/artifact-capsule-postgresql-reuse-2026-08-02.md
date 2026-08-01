# PostgreSQL artifact capsule reuse lab (2026-08-02)

## Result

The validation-carrying SQL capsule was exercised through the real
`GovernedPostgresExecutor` against PostgreSQL 16.12 (aarch64), not the earlier
SQLite-only mechanics fixture. The run created a temporary schema, a
`NOSUPERUSER NOBYPASSRLS` login role, an RLS-enabled table, and removed all of
them in a `finally` block.

Receipt: [`../results/artifact-capsule-postgresql-reuse-2026-08-02.json`](../results/artifact-capsule-postgresql-reuse-2026-08-02.json)

| Case | Result |
| --- | --- |
| valid capsule, bound parameter | accepted; one row |
| stale authorization epoch | denied (`authorization_epoch_mismatch`) |
| wrong authority scope | denied (`authority_scope_mismatch`) |
| expired capsule | denied (`expired`) |
| wrong parameter contract | denied (`parameter_contract_mismatch`) |
| schema drift after capsule creation | denied (`schema_fingerprint_mismatch`) |
| injection-shaped value | accepted as a bound value; zero rows; never interpreted as SQL |

All five denial cases failed closed. The executor applied read-only
transaction, `row_security=on`, governed `search_path`, statement/row/byte
limits, catalog validation, and PostgreSQL parameter binding. The receipt
contains hashes and aggregate metadata only.

## Claim boundary

This proves that a reusable artifact can be made to carry the minimum
authority, freshness, schema, parameter, and result-shape checks on PostgreSQL.
It does **not** prove that mined SQL is high quality, that result-shape checks
establish semantic equivalence, or that reuse improves task success. Those need
held-out task replay and human/SME adjudication.

## Reproduction

```sh
uv run python artifact_capsule_postgres_reuse.py \
  --output experiments/results/artifact-capsule-postgresql-reuse-2026-08-02.json
```

The default DSN targets the existing disposable local research container on
`127.0.0.1:55433`; set `CAPSULE_ADMIN_DSN` for another disposable PostgreSQL
instance. No production database or external data is touched.
