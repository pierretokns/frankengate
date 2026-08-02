# Termhood cross-cohort stability

## Question

Do deterministic termhood candidates recur across independent Claude trace
cohorts, or are they mostly cohort-specific and therefore unsafe as global
corporate aliases?

## Protocol

The probe runs the same deterministic token/document-frequency projection over
the Alin, Fable-5, Jobseek, and Wisp trace cohorts. It compares hashes of the
top 100 terms, acronym counts, and reformulation-candidate counts. No terms or
raw text are committed.

## Interpretation gate

High overlap can indicate shared harness boilerplate rather than shared
corporate meaning. Low overlap can indicate legitimate tenant-specific
vocabulary, sparse data, or extraction noise. Therefore this is a stability
diagnostic only; alias promotion still requires reviewed labels, NIL and
wrong-system negatives, temporal scope, and downstream replay utility.

## Result

The four cohorts produced 293 unique top-100 term hashes. **217** appeared in
only one cohort, **76** in at least two, and just **5** in all four. Pairwise
top-term Jaccard ranged from `.058201` (Jobseek/Wisp) to `.307190`
(Alin/Fable). The highest overlap is likely shared harness/skill boilerplate;
the low all-cohort overlap argues against a global alias table built from raw
trace frequency alone.

The practical direction is tenant/project-scoped candidate mining followed by
reviewed cross-scope linking, not automatic global ontology writes.

## Claim boundary

The probe does not estimate alias precision, enterprise concept quality,
semantic equivalence, or embedding lift.

Receipts:

- [content-free result](../results/termhood-cross-cohort-stability-2026-08-09.json)
- [independent verification](../results/termhood-cross-cohort-stability-verification-2026-08-09.json)
- [`termhood_cross_cohort_stability.py`](../../termhood_cross_cohort_stability.py)
