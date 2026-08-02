# Ontology-induction comparison matrix contract

Date: 2026-08-02  
Status: structural contract complete; no ontology efficacy claim

The study contract freezes a fair comparison between:

1. deterministic schema/identifier term mining;
2. GOI typed schema proposal;
3. OntoGPT/SPIRES population into a starter schema;
4. GraphRAG-style extraction; and
5. the staged governed pipeline.

All arms must use the same corpus receipts, candidate pool, principal/team/
project/source-system/time/template holdouts, two independent labels, and
changed-system replay receipts. The required metrics intentionally separate
structural coverage from entity/alias precision, relation evidence,
NIL-abstention, temporal and authority accuracy, replay success, wrong-system
rate, correction burden, cost, and latency.

The validator also rejects raw prompts, SQL, tool arguments, rows, documents,
and transcripts in committed manifests. The valid two-case fixture is
structurally valid but correctly promotion-blocked (`1` alias target, `0` hard
negatives, `1` NIL case, `0` changed-system replays). The invalid fixture fails
closed on missing holdouts/arms/receipts, raw content, and incomplete case
fields.

This contract is the next executable partner handoff. It does not imply that
GOI, OntoGPT, or GraphRAG has been run or that an ontology is correct. It
prevents structural coverage or graph density from being substituted for
identity, authority, temporal validity, or downstream utility.

Contract: [`ontology-induction-matrix-v1.json`](../../configs/studies/ontology-induction-matrix-v1.json)  
Validator: [`ontology_induction_matrix_validator.rb`](../../ontology_induction_matrix_validator.rb)  
Valid receipt: [`ontology-induction-matrix-valid-conformance-2026-08-02.json`](../results/ontology-induction-matrix-valid-conformance-2026-08-02.json)  
Invalid receipt: [`ontology-induction-matrix-invalid-conformance-2026-08-02.json`](../results/ontology-induction-matrix-invalid-conformance-2026-08-02.json)
