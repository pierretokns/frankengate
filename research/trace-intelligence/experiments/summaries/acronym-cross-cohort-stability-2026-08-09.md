# Acronym cross-cohort stability

## Question

Does the modernized AcronymExpansion-style extractor find definitions that
recur across independent trace cohorts, or does it mostly produce local review
candidates?

## Protocol

The same deterministic parenthetical-definition extractor was run over the
Alin, Fable-5, Jobseek, and Wisp cohorts. A candidate is counted as valid only
when the full form's initials agree with the acronym. Receipts store only
acronym/full-form hashes and aggregate counts; no transcript text is stored.

## Result

The extractor found 40 valid acronym hashes across the four cohorts, all in
exactly one cohort. It found 56 valid acronym/full-form pairs, again all in one
cohort; no pair of cohorts shared a valid acronym or an exact definition pair.
Per-cohort valid acronym counts were Alin 2/18 documents, Fable-5 29/115,
Jobseek 4/5, and Wisp 5/102. Fable-5 contained 10 ambiguous acronym hashes and
Jobseek contained 2; those candidates require abstention or review.

This is not evidence that the extractor is useless. It shows that contextual
definitions are sparse and highly cohort-local in these public traces. The
port can populate a scoped review queue, but a global acronym dictionary built
from these traces would have no observed cross-cohort support.

## Claim boundary

The probe does not estimate definition precision beyond the initials check,
enterprise concept quality, semantic equivalence, or downstream retrieval and
skill utility. Parenthetical definitions may be boilerplate, and missing
definitions are not proof that an acronym is invalid.

Receipts:

- [content-free result](../results/acronym-cross-cohort-stability-2026-08-09.json)
- [independent verification](../results/acronym-cross-cohort-stability-verification-2026-08-09.json)
- [`acronym_cross_cohort_stability.py`](../../acronym_cross_cohort_stability.py)
