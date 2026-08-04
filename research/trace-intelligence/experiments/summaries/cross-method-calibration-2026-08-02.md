# Cross-method calibration checkpoint

This checkpoint audits the 18 independently tracked mechanisms without
pooling unlike task metrics. It verifies receipt provenance and reports what
the existing evidence actually measures.

| Quantity | Coverage |
|---|---:|
| promotion-audit receipts | 18/18 |
| typed null classifications | 18/18 |
| paired effect receipts | 2 |
| comparable latency measurements | 0 |
| comparable token/currency cost measurements | 0 |

The two paired effects are:

- RHO: 8 paired LOCOMO tasks, mean delta `-0.2553`, paired SD `0.4792`, and a
  rough 80%-normal-power planning target of 28 pairs. This is a bounded
  negative result, not a universal rejection.
- BIRD trace-mined procedure: 20 paired exact-match tasks, mean delta `0.0`
  versus no-skill. This is a zero-headroom/no-lift result for that cohort.

The null taxonomy is deliberately typed: 9 mechanics/infrastructure-only, 4
negative-utility, 3 protocol/provider failures, and 2 underpowered/unproven.
No cost or latency value is synthesized when a receipt did not record a
comparable quantity. The result therefore does not authorize integration or a
cross-method ranking.

Machine receipt: `experiments/results/cross-method-calibration-2026-08-02.json`.
