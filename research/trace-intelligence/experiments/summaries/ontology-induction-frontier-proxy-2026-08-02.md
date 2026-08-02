# Frontier ontology-induction proxy

Date: 2026-08-02  
Status: completed mechanics probe; no ontology correctness claim

We first ran two public Fable Claude trace excerpts, then repeated the exact
protocol on five excerpts, through the same frontier model (`gpt-5.6-luna`)
using two independent structured-output arms. The five-document run is the
primary result below; the two-document run remains a pilot receipt.

- **GOI-style proposal:** schema-free typed entity/relation/constraint proposal.
- **OntoGPT-style population:** fixed starter types and relations, with
  unknown/omission allowed instead of inventing new classes.

The model returned valid structured output for all four calls. The receipt
contains only source/prompt/response hashes and aggregate counts; raw excerpts,
prompts, and responses remain external.

| arm | completed | mean entities | mean relations | evidence grounding | mean latency |
|---|---:|---:|---:|---:|---:|
| GOI-style proposal | 5/5 | 14.2 | 7.0 | **.951784** | 23.252s |
| OntoGPT-style population | 5/5 | 7.0 | 4.2 | .780952 | 17.737s |

The starter schema produced fewer entities and relations. In the two-document
pilot it had slightly better grounding, but in the five-document run the
GOI-style arm grounded more evidence (`.952` vs `.781`). This reverses the
pilot ordering and demonstrates that schema restriction is not itself a
faithfulness guarantee. Neither arm has independent ontology labels,
adjudicated aliases, principal/authority labels, temporal ground truth, NIL
calibration, or changed-system outcomes. Evidence substring grounding is a
mechanical faithfulness check, not semantic validation.

The first sandbox attempt failed before model execution because nested Codex
calls could not open the harness state database; the elevated retry succeeded.
That failure is recorded as an environment issue, not a quality result.

**Decision:** both approaches are viable proposal/population components. GOI
should remain a schema-draft arm; OntoGPT-style constrained population should
be preferred when a reviewed starter schema exists. Neither may write canonical
ontology edges or aliases without independent identity, temporal, authority,
and replay gates.

Primary receipt: [`ontology-induction-frontier-proxy-2026-08-02-r3.json`](../results/ontology-induction-frontier-proxy-2026-08-02-r3.json)

Pilot receipt: [`ontology-induction-frontier-proxy-2026-08-02-r2.json`](../results/ontology-induction-frontier-proxy-2026-08-02-r2.json)

Runner: [`ontology_induction_frontier_proxy.py`](../../ontology_induction_frontier_proxy.py)

Verifier: [`verify_ontology_induction_frontier_proxy.py`](../../verify_ontology_induction_frontier_proxy.py)
