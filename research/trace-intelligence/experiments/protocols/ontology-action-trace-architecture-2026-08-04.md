# Ontology/action trace architecture replay protocol

**Protocol ID:** `ontology-action-trace-architecture-v1`
**Status:** preregistered design; no utility claim yet
**Date:** 2026-08-04

## Hypotheses

- **H1:** typed object/link projections improve cross-user task and artifact
  retrieval over the current exact/lexical/dense baseline when the source pool
  contains composable evidence.
- **H2:** temporal and provenance edges lower stale or contradicted artifact
  acceptance during schema/tool drift.
- **H3:** graph-expanded retrieval lowers frontier adjudication calls while
  preserving semantic correctness and authorization safety.
- **H4:** modeling propose/approve/replay/promote/deprecate as explicit actions
  improves promotion precision compared with a proposal row alone.
- **H5:** schema-first ontology bootstrap is safer and more useful than
  free-form model-first ontology extraction.

## Factors and controls

The primary factor is representation, not model choice. Run A0–A8 from the
architecture matrix in the companion summary. Keep the same model, candidate
budget, database, authority epoch, and verifier. Include:

- no-graph A0 control;
- graph-without-vector A2 control;
- vector-without-graph A0/A4 comparison;
- formatting-only and no-proposal controls for the action loop;
- a schema-first versus model-first extraction comparison;
- a family-, user-, project-, system-, and time-disjoint holdout.

No arm may read sealed semantic labels, target SQL, or hidden action outcomes.

## Data contract

```text
object(object_id, object_type, canonical_key, scope, valid_from, valid_to,
       status, source_trace_id, extractor_version)
edge(edge_id, subject_id, predicate, object_id, confidence, evidence_ref,
     valid_from, valid_to, policy_epoch, assertion_status)
action(action_id, action_type, target_id, proposed_by, approved_by,
       input_snapshot, outcome_id, status, evidence_ref)
outcome(outcome_id, action_id, semantic_result, security_result,
        verifier_version, observed_at)
```

No raw prompt or SQL is committed in the receipt. Receipts contain counts,
hashes, aggregate metrics, and content-free evidence references only.

## Evaluation procedure

1. Import native trajectories and build the canonical DAG.
2. Project objects and edges deterministically from typed metadata and
   content-minimized narratives.
3. Run each retrieval arm under a fresh database snapshot and valid governed
   authority.
4. For each proposed artifact/eval/memory, record an action state rather than
   treating the proposal as a fact.
5. Replay accepted actions under changed schema/tool versions and independent
   PostgreSQL/security verification.
6. Re-run the same arms after injecting one rename, one stale edge, one
   contradiction, one NIL entity, and one unauthorized edge.
7. Aggregate only after overlap, authority, and sealed-label checks pass.

## Failure classifications

Use typed outcomes, not a single score:

- `representation_coverage_missing`
- `alias_or_nil_error`
- `wrong_system_link`
- `stale_edge_accept`
- `contradiction_suppressed`
- `unauthorized_node_or_edge`
- `semantic_execution_error`
- `unsafe_action`
- `action_outcome_unlinked`
- `frontier_overuse`
- `provider_or_harness_unavailable`

Provider or harness failures are infrastructure receipts and must not be
reported as memory, ontology, or skill-quality results.

## Promotion rule

Promote only if an arm improves the preregistered primary metric on the sealed
holdout with no increase in unauthorized exposure, stale acceptance, unsafe
action, or semantic error. Otherwise retain the projection as an experimental
debug/provenance view and keep A0 as the production path.
