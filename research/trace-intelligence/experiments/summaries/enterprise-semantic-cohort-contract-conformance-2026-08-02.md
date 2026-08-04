# Enterprise semantic-cohort contract and validator

## Why this artifact exists

The decisive open experiment is not another public vector benchmark. It is an
authorized, changed-system cohort with principal/team/project/system/time
holdouts, reviewed semantic labels, independent outcomes, and replay safety.
This contract makes those requirements machine-checkable before any model or
embedding result is admitted.

Contract: [`enterprise-semantic-cohort-v1.json`](../../configs/studies/enterprise-semantic-cohort-v1.json)

Validator: [`enterprise_semantic_cohort_validator.rb`](../../enterprise_semantic_cohort_validator.rb)

## Enforced requirements

- Raw prompts, SQL, tool arguments, rows, and transcripts remain outside the
  repository; committed manifests contain hashes and sealed URIs only.
- Candidate pools must be frozen before labels are unsealed.
- Every task binds principal, team, project, source system, source environment,
  changed environment, effective time, and source/changed authority epochs.
- Every trajectory has complete tool-result edges and a content-free receipt.
- Every task has an independently verified terminal-outcome receipt.
- Two independent labels are required from `exact`, `alias`, `semantic`,
  `wrong_scope`, `stale`, `nil`, or `unclear`; disagreements require third-SME
  adjudication.
- Deletion and retention receipts are mandatory.
- Promotion minimums are explicit: 100 targets, 50 hard negatives, and 25
  NIL/unclear cases, with user/team/project/system/time holdouts.
- The required comparison arms are no-artifact regeneration, strict
  fingerprinting, name-only negative control, reviewed semantic mapping, and
  reviewed mapping plus result validation.

## Conformance run

The valid two-task example passed structural validation while remaining
correctly **promotion-ineligible** because it has only one target and one hard
negative and no NIL/unclear cases. The receipt is:

[`enterprise-cohort-contract-conformance-2026-08-02.json`](../results/enterprise-cohort-contract-conformance-2026-08-02.json)

```json
{
  "structural_valid": true,
  "promotion_ready": false,
  "task_counts": {"target": 1, "hard_negative": 1},
  "promotion_blockers": [
    "target count 1 < 100",
    "hard_negative count 1 < 50",
    "nil_or_unclear count 0 < 25"
  ]
}
```

The intentionally incomplete negative fixture failed structural validation,
reporting missing consent scope, holdouts, arms, and tasks. This demonstrates
that “we have traces” is not enough to enter the causal study.
Its content-free receipt is
[`enterprise-cohort-invalid-conformance-2026-08-02.json`](../results/enterprise-cohort-invalid-conformance-2026-08-02.json).

## Decision

Use this contract as the partner handoff and ingestion gate. Public proxies can
populate mechanics and candidate-generation receipts, but they cannot satisfy
the promotion gate without the authorized labels, changed environments, and
independent outcomes defined here.

## Reproduction

```text
ruby enterprise_semantic_cohort_validator.rb \
  configs/studies/enterprise-semantic-cohort-v1.json \
  configs/studies/examples/enterprise-semantic-cohort-valid.json \
  experiments/results/enterprise-cohort-contract-conformance-2026-08-02.json
```
