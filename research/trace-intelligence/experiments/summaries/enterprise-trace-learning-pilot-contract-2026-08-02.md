# Enterprise trace-learning pilot contract

The current research has identified one decisive missing experiment: a paired,
changed-system study that tests artifact retrieval and skill consumption on the
same task set with independent semantic and terminal outcomes. This contract
turns that requirement into a machine-checkable partner handoff.

## Study shape

The valid manifest requires:

- retrieval arms: strict identifiers, lexical/termhood, dense, learned
  reranking, frontier review, and frontier review plus replay;
- artifact arms: no-artifact regeneration, strict fingerprint, name-only
  negative control, reviewed semantic mapping, and reviewed mapping plus
  result validation;
- skill arms: no skill, formatting placebo, reviewed skill, and generated
  skill;
- same-family, project-held-out, and changed-schema/authority splits;
- principal, team, project, system, time, and changed-authority holdouts;
- semantic success, authority safety, replay, NIL abstention, regressions,
  repair burden, user correction burden, acceptance, ranking, cost, latency,
  and reviewer-agreement metrics.

Promotion gates are preregistered at 100 targets, 50 hard negatives, 25
NIL/unclear cases, at least `.95` replay pass rate, zero unsafe accepts, at
most `.05` regression rate, at most `1.5×` cost/latency, and at least `.80`
reviewer agreement. These are study gates, not results.

## Conformance results

The valid plan is structurally valid but correctly **not promotion-ready**:
plan conformance cannot prove that a real authorized cohort, labels, replay
outcomes, or user outcomes exist. The intentionally invalid fixture fails
closed on raw-content leakage, missing holdouts and arms, missing gates, and
non-sealed output paths.

- [pilot contract](../../configs/studies/enterprise-trace-learning-pilot-v1.json)
- [valid partner manifest](../../configs/studies/examples/enterprise-trace-learning-pilot-valid.json)
- [valid-plan receipt](../results/enterprise-trace-learning-pilot-conformance-2026-08-02.json)
- [invalid fixture](../../configs/studies/examples/enterprise-trace-learning-pilot-invalid.json)
- [invalid-plan receipt](../results/enterprise-trace-learning-pilot-invalid-conformance-2026-08-02.json)
- [validator](../../enterprise_trace_learning_pilot_validator.rb)

## Why this matters

This contract prevents the common failure in the prior public studies: a
method can generate a plausible skill or rank a candidate while lacking a
compatible artifact, semantic label, authority validity, or changed-system
outcome. The partner study must measure those dimensions separately and keep
the proposer outside the evaluator.

## Claim boundary

The contract is an executable study scaffold, not evidence that the enterprise
cohort exists or that any skill, embedding, alias, or artifact improves users'
work. Promotion remains blocked until the sealed cohort passes the separate
semantic-cohort contract and all outcome gates.
