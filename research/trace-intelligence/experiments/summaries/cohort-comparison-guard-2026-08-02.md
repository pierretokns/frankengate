# Cohort comparison guard

Date: 2026-08-02  
Status: verified non-combination receipt

The schema-first ontology projection receipt and the existing dense/frontier
WMH-BIRD receipt share the same pinned trace and manifest hashes, but they are
not the same experiment. The projection uses 72 held-out tasks and the full
within-database split; the dense/frontier study uses a 44-case per-database
subset, a different candidate-pool description, and a different target/split
receipt.

The guard therefore reports `aligned=false` and rejects pooled metrics and any
claim that the two receipts demonstrate a combined cascade. Running with
`--require-aligned` exits non-zero as a deliberate fail-closed check.

Receipt: [`cohort-comparison-ontology-vs-dense-frontier-2026-08-02.json`](../results/cohort-comparison-ontology-vs-dense-frontier-2026-08-02.json)  
Runner: [`cohort_comparison_guard.py`](../../cohort_comparison_guard.py)

The next valid cascade study must freeze one candidate pool, one task subset,
one split, and one outcome-label contract before comparing lexical, typed,
dense, frontier, and replay arms.
