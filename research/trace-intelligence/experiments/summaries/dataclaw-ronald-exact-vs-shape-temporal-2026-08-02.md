# Exact command versus normalized-shape temporal reuse

## Protocol

This is the same per-project chronological 70/30 split used by the temporal
shape audit. The later fold is evaluated against earlier command evidence,
comparing a full-command SHA-256 digest with a normalized six-token command
shape. The comparison is content-free: only counts and hashes are retained.

## Results

| Measure | Exact command digest | Normalized shape |
|---|---:|---:|
| Evaluation events | 3,497 | 3,497 |
| Same-project event recurrence | **0.064** | **0.159** |
| Any-project event recurrence | **0.084** | **0.303** |
| Evaluation sessions with same-project recurrence | **0.629** | **0.838** |
| Evaluation sessions with any-project recurrence | **0.724** | **0.924** |

The normalized shape more than triples apparent any-project event reuse versus
exact command recurrence. Even exact recurrence is only a prior: an identical
command can be stale, unauthorized, run under a changed tool contract, or
wrong for the current task.

## Interpretation

The earlier session-level recurrence result was not an artifact-quality result.
The stronger exact-match control shows that much of the apparent reuse comes
from parameter variation and generic command prefixes. The correct ladder is:

```text
shape candidate -> exact/parameterized binding -> scope/epoch/schema gate
  -> independent replay -> validated artifact
```

Shape recurrence is useful for recall and hard-negative mining. Exact command
recurrence is a stronger prior but still cannot authorize reuse. A promotion
claim requires semantic labels and terminal outcomes on changed systems.

Receipt: [`dataclaw-ronald-exact-vs-shape-temporal-2026-08-02.json`](../results/dataclaw-ronald-exact-vs-shape-temporal-2026-08-02.json)

Audit implementation: [`dataclaw_exact_vs_shape_temporal_audit.rb`](../../dataclaw_exact_vs_shape_temporal_audit.rb)
