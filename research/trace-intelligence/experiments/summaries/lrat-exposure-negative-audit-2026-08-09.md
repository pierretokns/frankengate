# LRAT exposed-candidate negative audit (2026-08-09)

LRAT learns retrieval supervision from agent trajectories: documents exposed by
search but not subsequently browsed can be used as candidate negatives, while
browsed documents provide stronger positive evidence. This audit checks whether
that signal is actually present in the ten public sample trajectories shipped
with the [LRAT repository](https://github.com/Yuqi-Zhou/LRAT).

## Result

| Signal | Count |
|---|---:|
| Trajectories | 10 |
| Search calls | 102 |
| Browse calls | 28 |
| Distinct exposed documents | 624 |
| Distinct browsed documents | 26 |
| Exposed but unbrowsed candidates | 598 |
| Trajectories with an exposed/unbrowsed candidate | 10/10 |

The exposed-but-unbrowsed fraction is **0.958333**. The signal is therefore
available in the sample data and is suitable for a candidate-coverage
mechanics experiment.

## Boundary for Frankengate

An exposed-but-unbrowsed item is not automatically irrelevant. It may have been
skipped because of authority, cost, latency, redundancy, user choice, or an
already-satisfied subtask. LRAT's sample schema also has no independent
correctness, friction, NIL, wrong-system, principal, or authorization fields.
Therefore Frankengate should record exposure and refusal reasons explicitly and
use execution/SME outcomes before treating a candidate as a hard negative.

The result supports adapting LRAT's exposure-aware candidate sampling after
scope/identifier filtering; it does not justify importing LRAT's retrieval
training objective as an artifact-promotion or skill-learning mechanism.

## Receipts

- [machine-readable audit](../results/lrat-exposure-negative-audit-2026-08-09.json)
- [independent verification](../results/lrat-exposure-negative-audit-verification-2026-08-09.json)
- [runner](../../lrat_exposure_negative_audit.py)
- [verifier](../../verify_lrat_exposure_negative_audit.py)

Raw LRAT samples remain external; only hashes and aggregate counts are
committed.
