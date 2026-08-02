# Frontier ontology-induction proxy

Date: 2026-08-02  
Status: completed mechanics probe; no ontology correctness claim

We ran two public Fable Claude trace excerpts through the same frontier model
(`gpt-5.6-luna`) using two independent structured-output arms:

- **GOI-style proposal:** schema-free typed entity/relation/constraint proposal.
- **OntoGPT-style population:** fixed starter types and relations, with
  unknown/omission allowed instead of inventing new classes.

The model returned valid structured output for all four calls. The receipt
contains only source/prompt/response hashes and aggregate counts; raw excerpts,
prompts, and responses remain external.

| arm | completed | mean entities | mean relations | evidence grounding | mean latency |
|---|---:|---:|---:|---:|---:|
| GOI-style proposal | 2/2 | 16.0 | 7.5 | .888889 | 26.421s |
| OntoGPT-style population | 2/2 | 11.0 | 4.5 | .900000 | 20.952s |

The starter schema produced fewer entities and relations with slightly better
evidence grounding, which is consistent with constrained population reducing
free-form expansion. It does **not** show that the populated entities or
relations are correct. There are no independent ontology labels, adjudicated
aliases, principal/authority labels, temporal ground truth, NIL calibration,
or changed-system outcomes. Evidence substring grounding is a mechanical
faithfulness check, not semantic validation.

The first sandbox attempt failed before model execution because nested Codex
calls could not open the harness state database; the elevated retry succeeded.
That failure is recorded as an environment issue, not a quality result.

**Decision:** both approaches are viable proposal/population components. GOI
should remain a schema-draft arm; OntoGPT-style constrained population should
be preferred when a reviewed starter schema exists. Neither may write canonical
ontology edges or aliases without independent identity, temporal, authority,
and replay gates.

Receipt: [`ontology-induction-frontier-proxy-2026-08-02-r2.json`](../results/ontology-induction-frontier-proxy-2026-08-02-r2.json)  
Runner: [`ontology_induction_frontier_proxy.py`](../../ontology_induction_frontier_proxy.py)  
Verifier: [`verify_ontology_induction_frontier_proxy.py`](../../verify_ontology_induction_frontier_proxy.py)
