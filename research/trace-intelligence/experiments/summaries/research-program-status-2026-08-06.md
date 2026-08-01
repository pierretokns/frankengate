# Corporate trace-artifact learning status (2026-08-06)

This is the latest requirement-level status after the legacy TermSuite and
AcronymExpansion availability audit. The status is deliberately claim-bounded:
passing mechanics or proxy benchmarks do not establish enterprise utility.

## What the evidence supports today

- **Structured identity and governance are the strongest retrieval layer.**
  Exact identifiers, project/system scope, temporal versions, and authority
  checks outperform embedding-only retrieval on the tested collision cohorts.
- **Validated artifacts are technically viable.** SQL/tool capsules can be
  bound to parameters, schema versions, authorization, expiry, and independent
  replay checks. Changed-system stress tests show why semantic IDs are safer
  than name-only reuse.
- **Trace mining can generate review candidates.** Termhood, acronym extraction,
  friction signals, and action embeddings produce useful candidate queues. The
  TermSuite/Termolator and AcronymExpansion modernizations are reproducible
  current-Python baselines, not production-quality enterprise models.
- **Reviewed procedural guidance is directionally useful.** The six-instance
  SkillLearnBench composition replay passed its published verifier, but the
  changed-data repeat exposed a composition hard edge; this is not causal skill
  improvement.

## What is not established

- A custom corporate embedding model has not beaten the frozen structured
  baseline on a sufficiently large, independently labelled enterprise cohort.
- Cross-user discovery of “people doing the same work,” missing skills, or
  collaboration opportunities has no outcome-bearing evidence.
- Memory, generated skills, or frontier adjudication have not shown prospective
  user benefit or safe automatic promotion.
- Query expansion and older term/acronym methods have only synthetic or
  silver-label transfer evidence; they must remain review-only.

## Current proof gaps

The independent completion audit leaves these requirements open:

1. powered task/user/time-disjoint controls;
2. an authorized changed-system cohort with independent terminal outcomes; and
3. comparable model/embedding cost, latency, power, and typed NIL/error
   calibration.

The next decisive experiment is therefore a single frozen, consented cohort
with exact/structured, dense, candidate-mining, composable, and frontier arms.
Adding another database or another embedding index before that cohort would not
answer the unresolved research question.

## Integrity

- Full suite: `702 passed, 11 skipped, 12 warnings`.
- Completion receipt: [`program-completion-audit-2026-08-06.json`](../results/program-completion-audit-2026-08-06.json)
- Legacy upstream availability: [`legacy-term-acronym-upstream-availability-2026-08-06.md`](legacy-term-acronym-upstream-availability-2026-08-06.md)
- Detailed objective audit: [`objective-completion-audit-2026-08-04.md`](objective-completion-audit-2026-08-04.md)

Raw user trace content remains outside the repository.
