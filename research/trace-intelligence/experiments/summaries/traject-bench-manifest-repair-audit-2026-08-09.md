# TRAJECT-Bench candidate-manifest repair audit (2026-08-09)

The lexical retrieval baseline exposed a benchmark coverage problem: some
reference tool names are not present in the published domain or global tool
manifests. This audit checks whether those names can be repaired by exact or
uniquely normalized matching. It does **not** apply fuzzy matching or change
benchmark labels.

## Result

| Measure | Count |
|---|---:|
| Reference records | 5,910 |
| Records with all target names exactly in `all_tools.json` | 5,337 |
| Records repairable by unique normalization only | 18 |
| Records still unresolved | 555 |
| Missing name occurrences | 735 |
| Missing name occurrences uniquely normalized | 18 |
| Unresolved name occurrences | 717 |
| Distinct missing name strings | 56 |
| Distinct repair pairs | 4 |

The unresolved cases are concentrated repeated fixture names, not random
singletons. The common repairable cases are presentation differences such as
spacing or capitalization. The unresolved cases require source-manifest
republication or explicit adjudication; guessing from fuzzy similarity would
contaminate the retrieval labels.

## Decision

The fair retrieval comparison must either:

1. obtain the missing tool definitions from the benchmark maintainers and pin a
   repaired manifest; or
2. publish an eligibility split that excludes unresolved records in advance.

It must not silently map them by fuzzy name similarity. The current lexical
receipts therefore remain valid only for their explicitly eligible records.

Receipt: [`traject-bench-manifest-repair-audit-2026-08-09.json`](../results/traject-bench-manifest-repair-audit-2026-08-09.json)
