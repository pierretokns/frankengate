# SkillLearnBench changed-data frontier replay

Date: 2026-08-06  
Task: `enterprise-information-search-1`  
Mutation: deterministic product rename `ContentForce` → `ContentHub` in the
prompt and data fixture  
Model: `gpt-5.6-luna` through the Codex subscription

## Result

| arm | q1 recall | q1 precision | q3 exact | published verifier |
|---|---:|---:|---:|---:|
| null | `1.000` | `.889` | `1/1` | pass (one false positive) |
| reviewed human | `1.000` | `1.000` | `1/1` | pass |
| reviewed + generated composite | `.875` | `1.000` | `1/1` | fail (one missing ID) |

All arms produced valid JSON and exact q3 answers. The human-authored
procedure preserved full q1 recall and removed the null false positive after
the product rename. The composite retained precision but missed one expected
q1 ID.

## Interpretation

This is a one-task public changed-data proxy, not proof of enterprise transfer
or a causal skill effect. It does establish a useful hard edge: composing more
procedures is not automatically more robust under changed names/data; the
reviewed procedure alone was stronger on this mutation. A fair next test needs
multiple renamed/added/deleted/semantically-drifted fixtures, task-disjoint
families, and independent changed-system verifiers before promoting composition.

Receipt: [`skilllearnbench-changed-data-frontier-2026-08-06.json`](../results/skilllearnbench-changed-data-frontier-2026-08-06.json)
