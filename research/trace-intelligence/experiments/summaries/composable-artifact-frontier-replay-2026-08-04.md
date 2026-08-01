# Composable validated-artifact frontier replay

**Status:** promising bounded signal; not a promotion result
**Cohort:** five source-disjoint broker tasks, replayed with two seeds
**Model/harness:** direct Codex native JSON frontier harness
**Authority:** governed PostgreSQL, current epoch, independent semantic verifier

## Result

The trace-mined arm supplied validated source-query subplans and composition
instructions, but was not allowed to copy a whole source query. Across the two
seeds (10 episode runs total):

| Arm | Semantically correct | SQL attempts | Tool calls | Unauthorized observations |
|---|---:|---:|---:|---:|
| No skill | 7/10 | 13 | 33 | 0 |
| Formatting placebo | 6/10 | 14 | 34 | 0 |
| Composable trace-mined procedure | **10/10** | **10** | **30** | 0 |

The independent verifier passed both seeded receipts. The candidate had stable
wins on three of five unique tasks against each control, no stable losses, and
two ties-or-mixed tasks. Both seeds used the same five target tasks, so they are
replications, not ten independent tasks.

Machine-readable aggregate:
[`composable-artifact-frontier-replay-2026-08-04-aggregate.json`](../results/composable-artifact-frontier-replay-2026-08-04-aggregate.json)

## Interpretation

This is the first positive signal for **composable** artifact reuse after the
whole-query retrieval and library-coverage nulls. It suggests that a validated
artifact library can help a frontier agent compose a new answer even when no
single stored query is semantically reusable. It does not prove causal skill
improvement, cross-family transfer, enterprise utility, or that the procedure
would help a different model.

The result is consistent with the Palantir/Semantica action/ontology direction:
the useful unit may be a typed, provenance-bearing subplan or relation rather
than a nearest-neighbor whole-query memory. The next test must vary database
family, project, time, and schema; compare a parameterized artifact library and
frontier regeneration; and include negative-transfer, stale-edge, and NIL cases.
