# Skill-in-use and bounded verifier contract

This protocol turns the recent skill-lifecycle literature into a testable
Frankengate experiment. It separates a stored artifact from its use in a
specific run, and separates a model's proposal from the independent outcome
decision.

## Run record

Every exposed skill or artifact use produces one immutable content-minimized
record:

```json
{
  "run_id": "opaque-run-id",
  "proposal_id": "opaque-proposal-id",
  "skill_id": "opaque-skill-id",
  "activation": {"reason_code": "matched_trigger", "rank": 1},
  "binding": {
    "tenant": "opaque-tenant",
    "project": "opaque-project",
    "system_id": "opaque-system",
    "authority_epoch": "opaque-epoch",
    "schema_fingerprint": "opaque-schema"
  },
  "exposure": {"arm": "reviewed_artifact", "turns": 3},
  "verifier_observation": {
    "outcome_class": "semantic_match",
    "error_class": null,
    "authority_class": "authorized",
    "schema_class": "compatible",
    "result_shape_hash": "opaque-hash",
    "repair_count": 0,
    "next_action_allowed": true
  },
  "independent_replay": {"status": "pending", "receipt_id": "opaque-receipt"},
  "release": {"status": "quarantined", "artifact_hash": "opaque-hash"}
}
```

The binding and exposure fields are evaluated before ranking or model
consumption. Raw prompts, SQL, rows, credentials, unrestricted provider errors,
and hidden gold answers stay outside the proposer-visible record.

## Allowed enums

- `outcome_class`: `success`, `semantic_match`, `semantic_mismatch`,
  `abstain`, `unknown`.
- `error_class`: `none`, `syntax`, `schema`, `timeout`, `tool_contract`,
  `policy`, `authority`, `unknown`.
- `authority_class`: `authorized`, `stale_epoch`, `wrong_scope`, `revoked`,
  `unknown`.
- `schema_class`: `compatible`, `renamed`, `drifted`, `missing`, `unknown`.
- `independent_replay.status`: `pass`, `fail`, `abstain`, `pending`.
- `release.status`: `quarantined`, `canary`, `released`, `rolled_back`.

## Non-negotiable invariants

1. A proposer cannot write or validate its own replay receipt.
2. `authority_class` must be `authorized` and the epoch must be current before
   any candidate is executed or included in an aggregate.
3. `next_action_allowed=false` for stale, revoked, wrong-scope, or incompatible
   bindings; the model cannot override this value.
4. A verifier observation is evidence attached to the run, not a mutable
   memory or global alias edge.
5. A release requires independent replay, a reviewed or otherwise admitted
   artifact provenance chain, and no unsafe acceptance on the negative set.
6. Any generated skill influenced by a run is excluded from that run's causal
   evaluator and from its own validation set.
7. Deletion or withdrawal removes the run's derived visibility and invalidates
   all descendant proposals.

## Minimum factorial

Run the same family-disjoint tasks under:

```text
no_skill | formatting_placebo | reviewed_artifact | generated_skill
       × no_verifier | bounded_verifier | independent_replay
       × same_family | project_held_out | changed_schema_or_epoch
```

Use identical model, harness, horizon, tool budget, and evaluator. Report
paired semantic success, unsafe acceptance, abstention, repair burden,
negative transfer, cost, latency, and reviewer agreement. A skill-text quality
score or valid JSON response is not a positive outcome.

## Admission and promotion gates

Admission requires complete tool calls/results, reset or checkpoint state,
task-family and time split, authority/schema binding, and an independent
terminal evaluator. A candidate is promotable only if it beats both no-skill
and placebo on held-out families, has zero unsafe accepts in the release set,
and does not exceed the preregistered regression floor for cost, latency, or
repair burden. Otherwise it remains quarantined with a typed reason.

## Relation to current evidence

- The existing [enterprise outcome gate](../../enterprise_outcome_gate.py) and
  its conformance runner already implement current-epoch, scope, consent,
  cohort, and reviewed-label fail-closed mechanics.
- The [dream release pipeline](../../dream_release_pipeline_v2.py) already
  enforces independent verification, copy-on-write release, provenance, and
  deletion-aware visibility for generated proposals.
- Changed-system typed replay already demonstrates the authority/compatibility
  portion of this contract; it does not establish skill utility.
- BIRD and ALFWorld runs demonstrate why replay outcomes and task-family splits
  are required; most prior procedure arms were null or negative.
- The dense/frontier and identifier studies provide candidate-generation arms,
  not consumption or outcome evidence.

This protocol is the bridge from the literature refresh to the consent-gated
enterprise outcome pilot. It is intentionally small enough to implement in the
existing replay/evaluation harness before introducing a new database or
embedding service.
