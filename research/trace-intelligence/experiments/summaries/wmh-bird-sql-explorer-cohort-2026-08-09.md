# WMH-BIRD SQL explorer cohort (2026-08-09)

This is the larger task-disjoint follow-up to the eight-case SQL explorer
bridge. It evaluates a separate frontier explorer over all exposed table names
for four held-out traces per database family. Gold SQL and replay outcomes stay
outside the prompt; each selected table is independently checked against the
pinned SQLite database.

## Protocol

- `44` successful traces from `11` database families (`4` per family).
- Within each database, deterministic odd/even task split; only the odd half is
  evaluated, with no task repeated from the even half.
- Candidate pool is every table exposed in the trace.
- Explorer: Luna, shortlist cap `8`.
- Lexical control: same pool, table-name lexical top-8.
- Strict target: table references in recorded SQL.
- Compatibility target: strict target plus exposed tables whose substitution
  independently preserves the query result. This is query-local compatibility,
  not semantic alias truth.

## Pooled results

| Arm | Strict MRR | Strict R@1 | Strict R@5 | Compatible selected rate | Invalid selected tables | Mean selected |
|---|---:|---:|---:|---:|---:|---:|
| Lexical top-8 | .796266 | .704545 | .886364 | .391153 | 3.727273 | 5.545 |
| Separate explorer | **.965909** | **.931818** | **1.000000** | **.924242** | **.227273** | **2.068** |

The explorer’s strict MRR improved by `+.169643` and Recall@1 by `+.227273`,
while selecting roughly `63%` fewer tables. It did not simply reorder a fixed
candidate list: it reduced invalid exposed-table selections and recovered
targets that lexical ranking missed.

## Per-family result

| Database family | Lexical MRR / R@1 | Explorer MRR / R@1 | Explorer compatible rate |
|---|---:|---:|---:|
| California Schools | .875 / .750 | 1.000 / 1.000 | 1.000 |
| Card Games | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 |
| Codebase Community | .494 / .250 | 1.000 / 1.000 | 1.000 |
| Debit Card Specializing | 1.000 / 1.000 | .750 / .500 | .792 |
| European Football | .833 / .750 | 1.000 / 1.000 | 1.000 |
| Financial | 1.000 / 1.000 | 1.000 / 1.000 | .917 |
| Formula 1 | .531 / .500 | 1.000 / 1.000 | .917 |
| Student Club | .567 / .500 | 1.000 / 1.000 | 1.000 |
| Superhero | .833 / .750 | 1.000 / 1.000 | 1.000 |
| Thrombosis Prediction | .750 / .500 | .875 / .750 | .750 |
| Toxicology | .875 / .750 | 1.000 / 1.000 | .792 |

The exceptions matter. Debit Card and Thrombosis show that the explorer is not
universally superior; the next study must report family-stratified failures and
not ship a pooled-only policy.

## Evidence boundary

This is materially stronger than the earlier eight-case bridge, but it remains
a public mechanics proxy:

- BIRD questions include hints and are not enterprise intent labels;
- SQLite result preservation is not semantic equivalence, authorization, or
  user utility;
- there are no principals, authority epochs, schema versions, human labels, or
  changed-system outcomes; and
- frontier latency and billing were not recorded in this receipt.

The result supports a **candidate-generation/noise-reduction hypothesis**, not
automatic artifact promotion, alias learning, embedding training, or skill
transfer.

## Next decisive test

Run the same frozen explorer and lexical arms on a licensed enterprise cohort
with principal/project/system/time holdouts, explicit exposure sets, authority
epochs, same-surface/wrong-system and NIL candidates, schema/temporal changes,
and independent replay. Treat a selected artifact as useful only when the
changed-system validator passes. Include no-explorer, explorer, explorer-plus-
dense, and frontier-review arms under fixed cost and latency budgets.

## Receipts

- [machine-readable cohort result](../results/wmh-bird-sql-explorer-cohort-2026-08-09.json)
- [independent verification](../results/wmh-bird-sql-explorer-cohort-verification-2026-08-09.json)
- [runner](../../wmh_bird_sql_explorer_cohort.py)
- [verifier](../../verify_wmh_bird_sql_explorer_cohort.py)

Raw frontier outputs remain external under `/private/tmp`; only hashes,
identifiers, and aggregate metrics are committed.
