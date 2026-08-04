# Enterprise semantic-cohort contract addendum

Date: 2026-08-10  
Status: contract strengthened; no authorized cohort yet

The cohort contract now requires mutation-stratum coverage in addition to the
existing target, hard-negative, NIL/unclear, holdout, authority, dual-label,
outcome, deletion, and retention gates. The required strata are:

```text
no_change
additive_field_or_parameter
approved_rename
same_surface_collision
changed_join_grain_or_result_meaning
stale_or_revoked_authority
changed_tool_contract
```

Each requires at least five tasks in the minimum study slice. This closes a
failure mode exposed by the public experiments: a cohort can have many
gold-SQL targets and generic negatives while still containing no reviewed
same-surface, temporal, wrong-system, or changed-contract cases. Such a
cohort cannot fairly evaluate aliases, hard-negative training, embeddings, or
artifact reuse.

The updated validator was run against both fixtures:

- The valid example remains structurally valid but promotion-blocked. It now
  reports the missing mutation strata explicitly (`no_change`, additive drift,
  changed join/result meaning, stale/revoked authority, and changed tool
  contract, plus insufficient counts for the two included strata).
- The invalid example fails closed on missing consent, holdouts, arms, tasks,
  and promotion counts.

Receipts:

- Contract: [`enterprise-semantic-cohort-v1.json`](../../configs/studies/enterprise-semantic-cohort-v1.json)
- Validator: [`enterprise_semantic_cohort_validator.rb`](../../enterprise_semantic_cohort_validator.rb)
- Valid conformance: [`enterprise-semantic-cohort-conformance-2026-08-10.json`](../results/enterprise-semantic-cohort-conformance-2026-08-10.json)
- Invalid conformance: [`enterprise-semantic-cohort-invalid-conformance-2026-08-10.json`](../results/enterprise-semantic-cohort-invalid-conformance-2026-08-10.json)

This is a study-readiness improvement, not evidence that an embedding, alias
model, skill, or artifact is useful. The next step remains obtaining the
authorized data and independent semantic/outcome labels.
