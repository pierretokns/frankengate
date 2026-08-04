# WMH-BIRD SQL separate-explorer probe (2026-08-09)

This is the first bridge from the generic separate-explorer test to validated
SQL artifacts. Luna saw only the natural-language question and all table names
exposed in the trace. It did not see the recorded SQL, target labels, replay
results, or any tool output. The evaluator independently replayed every selected
table substitution on the pinned SQLite databases.

## Protocol

- Eight database families, one successful trace per family, two independent
  Luna runs (`16` frontier calls total).
- Mean exposed candidate pool: `7` tables; maximum: `13`.
- The case selector preferred a trace with a result-preserving exposed-table
  substitution when that database contained one. Only Financial (`trans`) and
  Formula 1 (`results`) had such alternatives in this sample; six cases had no
  replay-equivalent alternative.
- Explorer shortlist cap: eight tables.
- Strict target: tables referenced by the recorded SQL.
- Compatibility target: strict target plus an exposed table whose substitution
  independently returned identical rows for at least one used table.
- A compatibility match is query-local replay evidence, not a semantic alias or
  authorization decision.

## Results

| Arm | Strict MRR | Strict R@1 | Compatible MRR | Compatible selected rate | Invalid selected tables | Mean selected |
|---|---:|---:|---:|---:|---:|---:|
| Lexical top-8 | .837500 | .750000 | .837500 | .418006 | 3.875 | 6.375 |
| SQL explorer, run 1 | 1.000000 | 1.000000 | 1.000000 | .958333 | .125 | 2.625 |
| SQL explorer, run 2 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000 | 2.375 |
| SQL explorer mean | **1.000000** | **1.000000** | **1.000000** | **.979167** | **.0625** | **2.500** |

The selected-set Jaccard across the two runs was `.895833`, with exact
shortlist agreement on `6/8` cases. On this small public proxy, the explorer
found every recorded target at rank one while selecting fewer tables and almost
eliminating replay-incompatible selections.

## Why this is promising but not yet a product result

The result is stronger than the generic tool probe because the acceptance
signal includes independent SQL replay. It still has important limits:

- only eight cases were evaluated;
- the questions contain BIRD hints that may make table names unusually easy;
- target traces were selected per database rather than from a fully held-out
  enterprise task distribution;
- result-preserving alternatives are query-local compatibility, not user intent;
- there are no principal, authority epoch, schema-version, human utility, or
  changed-system labels; and
- frontier cost and latency were not recorded in this v1 receipt.

Therefore this does **not** establish semantic alias quality, safe artifact
reuse, embedding value, or skill transfer. It establishes a useful next-stage
hypothesis: a compact frontier explorer may reduce candidate noise before
replay and structured validation.

## Frankengate decision and next gate

Keep the explorer behind the structured scope/identifier layer. For a real
cohort, it must emit table/tool IDs and evidence spans, never executable SQL;
then the deterministic validator must check parameters, authority, freshness,
and changed-system replay. Compare no explorer, lexical/identifier, explorer,
explorer-plus-dense, and replay-gated promotion under principal/project/system/
time holdouts. Add same-surface wrong-system, temporal replacement, NIL, and
stale-authority cases before training any model.

This directly advances [artifact reuse #119](https://github.com/pierretokns/frankengate/issues/119),
[changed-system replay #118](https://github.com/pierretokns/frankengate/issues/118),
[hard-negative mining #123](https://github.com/pierretokns/frankengate/issues/123), and
[identifier-aware representations #124](https://github.com/pierretokns/frankengate/issues/124).

## Receipts

- [run 1 result](../results/wmh-bird-sql-explorer-probe-2026-08-09.json)
- [run 1 verification](../results/wmh-bird-sql-explorer-probe-verification-2026-08-09.json)
- [run 2 result](../results/wmh-bird-sql-explorer-probe-r2-2026-08-09.json)
- [run 2 verification](../results/wmh-bird-sql-explorer-probe-r2-verification-2026-08-09.json)
- [aggregate](../results/wmh-bird-sql-explorer-probe-aggregate-2026-08-09.json)
- [aggregate verification](../results/wmh-bird-sql-explorer-probe-aggregate-verification-2026-08-09.json)
- [runner](../../wmh_bird_sql_explorer_probe.py)
- [run verifier](../../verify_wmh_bird_sql_explorer_probe.py)
- [aggregate runner](../../aggregate_wmh_bird_sql_explorer_probe.py)
- [aggregate verifier](../../verify_wmh_bird_sql_explorer_aggregate.py)

Raw model outputs remain external under `/private/tmp`; only aggregate metrics,
table identifiers, and hashes are committed.
