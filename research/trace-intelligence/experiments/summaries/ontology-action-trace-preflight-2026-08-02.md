# Ontology/action trace comparison preflight

Date: 2026-08-02  
Status: structurally valid preflight; no ontology utility claim

The existing ontology/action protocol was previously only a prose design. This
preflight freezes the independent representation arms and promotion boundaries
before any frontier extraction or graph implementation is run.

## Frozen arms

- `A0`: canonical trajectory DAG plus current exact/lexical/dense retrieval;
- `A1`: typed objects only;
- `A2`: temporal/provenance graph only;
- `A3`: objects + graph + full-text search;
- `A4`: objects + graph + full-text search + pgvector;
- `A5`: A4 plus query-time ontology path constraints;
- `A6`: A5 plus propose/approve/replay/promote/deprecate action states;
- `A7`: schema-first ontology bootstrap;
- `A8`: schema-first bootstrap plus frontier refinement.

The contract requires project/system/user/time holdouts, target/hard-negative/NIL/
unclear strata, changed schema or authority replay, evidence-linked edges,
validity intervals, policy epochs, and zero tolerance for unauthorized edges or
unsafe actions. It keeps PostgreSQL + JSONB + FTS + pgvector as the projection
store and does not introduce a graph database before graph expansion is shown
to be the bottleneck.

## Verification

The valid fixture passed structural conformance. The invalid fixture failed
closed on local/raw URIs, missing arms and holdouts, committed raw content,
unsafe promotion thresholds, missing replay, and non-canonical storage choices.
The receipt is content-free and deliberately reports `promotion_ready=false`:
this proves only that the study can be run consistently, not that an ontology
or graph will improve enterprise work.

## Next execution

Run the arms on the frozen authorized semantic cohort and a synthetic changed-
system fixture. Do not open labels to the proposer, do not pool representation
arms with model-tuning arms, and do not promote any extracted edge until it has
evidence support, temporal/authority checks, and independent replay.

