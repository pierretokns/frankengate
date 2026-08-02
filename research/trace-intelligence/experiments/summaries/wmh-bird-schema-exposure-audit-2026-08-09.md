# WMH-BIRD schema-exposure audit (2026-08-09)

This audit adapts LRAT's exposure-aware supervision idea to the public
WMH-BIRD SQL-agent traces. The trace contains schema output from the `bash`
tool and a recorded candidate SQL answer. A schema table is treated as
exposed; a table referenced by the candidate SQL is treated as consumed. The
remaining exposed tables are candidate negatives only.

## Result

Across **1,993** recorded traces:

- **11,707** schema-table exposures;
- **3,850** consumed table identifiers;
- **7,857** exposed-but-unconsumed table identifiers (**67.1%**);
- **1,910/1,993** traces contained at least one exposed-but-unconsumed table;
- recorded rewards were `1.0` for 1,345 traces and `0.0` for 648 traces.

This is a much closer fit to Frankengate's SQL artifact problem than the LRAT
web-search samples: schema candidates and SQL consumption are in the same
trace family, and the corpus has recorded tool observations and reward fields.

## Boundary

An unconsumed table is not a semantic hard negative. The agent may have skipped
it because of query intent, schema redundancy, authority, cost, or an early
mistake. The public cache used here also lacks the external database archive,
so this audit does not independently validate SQL correctness or artifact
reuse.

The useful next experiment is to join these exposure candidates to the
reconstructable database and gold-result validator: compare exposure-aware
negative sampling with same-surface/wrong-system and family-held-out negatives,
then measure retrieval and independent execution—not just table overlap.

## Receipts

- [machine-readable audit](../results/wmh-bird-schema-exposure-audit-2026-08-09.json)
- [independent verification](../results/wmh-bird-schema-exposure-audit-verification-2026-08-09.json)
- [runner](../../wmh_bird_schema_exposure_audit.py)
- [verifier](../../verify_wmh_bird_schema_exposure_audit.py)

Raw WMH-BIRD traces remain external; only hashes and aggregate metrics are
committed.
