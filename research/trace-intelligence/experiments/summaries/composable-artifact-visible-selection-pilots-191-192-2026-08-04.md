# Visible-selection composable-artifact pilots 191/192

**Status:** preserved for audit; excluded from causal aggregation
**Classification:** `domain_valid_visible_selection_pilot`

These three content-minimized receipts were produced during protocol setup on
single broker tasks. They are useful mechanics traces but are not evidence of
held-out transfer: they carry one task each, have no independent semantic
verifier comparison, and the candidate was selected visibly. They must not be
combined with the authoritative two-seed replay.

| Receipt | Arm | Semantic result | SQL attempts | Tool calls | Authority |
| --- | --- | ---: | ---: | ---: | --- |
| `191` | no-skill | 1/1 | 2 | 4 | valid |
| `191` | formatting placebo | 0/1 | 3 | 5 | valid |
| `191` | compiled procedure | 1/1 | 1 | 3 | valid |
| `191-candidate` | compiled procedure | 1/1 | 1 | 3 | valid |
| `192` | no-skill | 0/1 | 1 | 3 | valid |
| `192` | formatting placebo | 1/1 | 1 | 3 | valid |
| `192` | compiled procedure | 1/1 | 1 | 3 | valid |

The receipts contain hashes and aggregate fields only. They are retained to
make the research history complete, but the promotion boundary remains the
independently verified, source-disjoint two-seed replay in
[`composable-artifact-frontier-replay-2026-08-04.md`](composable-artifact-frontier-replay-2026-08-04.md).
