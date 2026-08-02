# Same-candidate composable artifact lineage audit — 2026-08-02

## What this closes

The earlier lifecycle audit had no candidate whose identity could be followed
from review into replay.  The authoritative composable replay fixture does
provide one: artifact ID
`400115bd469d4d39da6c85c8924f0f3a90e7cfc9eb0724997139e93faf019019` is present
in both the seed-840000 and seed-850000 receipts.

## Same-candidate result

| check | seed 840000 | seed 850000 |
|---|---:|---:|
| candidate semantic correctness | `5/5` | `5/5` |
| candidate authority-valid executions | `5/5` | `5/5` |
| unauthorized observations | `0` | `0` |
| independent semantic verifier | passed | passed |
| no-skill control | `3/5` | `2/5` |
| formatting-placebo control | `3/5` | `2/5` |

The candidate hash, task set, database family, and arm set are identical across
seeds.  This is stronger than an aggregate count: the same immutable candidate
was replayed twice and independently recomputed against governed PostgreSQL.

## Integrity finding and manifest reconstruction

The aggregate receipt declares the source and target task families disjoint,
but both underlying seed receipts retain an older “visible-selection pilot”
claim boundary and do not independently carry the disjointness field.

I independently reconstructed the split from the pinned cohort manifest and
the content-minimized candidate metadata:

- source rows: `19` (`instruct_basic_postgres.csv` + `instruct_advanced_postgres.csv`);
- source validation failures: `1` (`SQLPolicyError`);
- candidate artifacts: `18` (exactly `19 − 1`);
- target rows: `5` (`questions_gen_postgres.csv`);
- replay target rows: `5`, matching the manifest task hashes;
- source/target task-hash intersection: `0`.

Therefore the underlying data split is verified, while the seed-level claim
metadata remains stale and must be regenerated before calling the receipt
self-consistent.  The seed protocol-remediation fields carry the same
family-disjoint study ID and candidate hash, so replay mechanics are coherent;
the remaining issue is provenance metadata, not evidence of data overlap.

## What is proven

- immutable candidate identity survives two seeded replays;
- independent semantic recomputation agrees with both stored results;
- governed authority checks pass and unauthorized observations remain zero;
- the candidate has a positive same-family result on this five-task fixture;
- no-skill and formatting-placebo controls are present.

## What remains open

- reconcile the seed-level claim boundaries and regenerate the aggregate receipt;
- replay the same candidate under changed schemas/systems;
- obtain independent SME semantic labels;
- test cross-family and cross-project transfer;
- record a versioned release/rollback event for this candidate;
- measure prospective next-task utility and correction burden.

This is therefore a verified same-family replay lineage, not a promotion or
causal enterprise skill-learning result.

## Receipts

- [lineage audit](../results/composable-candidate-lineage-audit-2026-08-02.json)
- [independent verification](../results/composable-candidate-lineage-audit-verification-2026-08-02.json)
- [authoritative replay summary](composable-artifact-frontier-replay-2026-08-04.md)
- [runner](../../composable_candidate_lineage_audit.py)
- [verifier](../../verify_composable_candidate_lineage_audit.py)
