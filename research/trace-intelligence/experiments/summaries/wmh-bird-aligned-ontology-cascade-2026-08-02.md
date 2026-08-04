# WMH-BIRD aligned ontology versus dense/frontier comparison

Date: 2026-08-02  
Status: aligned public-proxy result; no enterprise promotion claim

The schema-first ontology arms were rerun on the frozen 44-case cohort and
passed the cohort guard against the existing dense/frontier receipt: identical
source hashes, task subset, split, candidate pool, and target contract.

| Arm | MRR | Recall@1 | Recall@5 |
| --- | ---: | ---: | ---: |
| A0 lexical | 0.7963 | 0.7045 | 0.8864 |
| A1 schema-first typed identifiers | 0.9489 | 0.9091 | 1.0000 |
| A2 provenance/alias edges | 0.8144 | 0.7273 | 0.9091 |
| A3 typed + alias | 0.9464 | 0.9091 | 0.9773 |
| A6 replay-backed action evidence | 0.9464 | 0.9091 | 0.9773 |
| A7 schema-first bootstrap | 0.9489 | 0.9091 | 1.0000 |
| Dense Nomic | 0.9402 | 0.9091 | 1.0000 |
| Frontier Luna | 0.9545 | 0.9091 | 1.0000 |

The aligned comparison gives a stronger result than the earlier cross-cohort
summary: schema-first typed identifiers slightly beat dense retrieval on MRR
(`0.9489` vs. `0.9402`) and nearly match frontier ranking (`0.9545`), while
alias edges alone are materially weaker. Frontier's distinct contribution in
the existing receipt is shortlist precision/noise reduction: replay-compatible
selection was `0.9280` for frontier versus `0.4082` for dense, with average
shortlist sizes of `2.0` versus `5.55`.

This is still **not** a combined sequential cascade result. The frontier arm
was run as a separate full-pool reviewer, not on the typed/dense shortlist;
the study has no human alias labels, principals, authority epochs, or changed
systems. The defensible design implication is:

```text
schema/exact identifiers -> optional dense recall -> frontier compression -> replay
```

The interaction and cost claim remains pending a same-candidate sequential
run. The result and the independent cohort-alignment guard are the evidence
needed to run that next without cohort drift.

Receipts:

- [aligned ontology result](../results/ontology-action-trace-aligned-cohort-2026-08-02.json)
- [dense/frontier result](../results/wmh-bird-sql-dense-frontier-cohort-2026-08-09.json)
- [alignment guard](../results/cohort-comparison-ontology-vs-dense-frontier-2026-08-02.json)
- [aligned cohort manifest](../../configs/experiments/wmh-bird-aligned-cascade-cohort-v1.json)
