# CASS prior-research architecture refresh

**Date:** 2026-08-04
**Purpose:** recover the Palantir, Semantica-AGI, TypeGraph, and related
architecture work from the local CASS archive, then identify experiments that
are genuinely new relative to the current trace-artifact program.

## Evidence recovered

The source material is local CASS history, not a fresh claim about a vendor
implementation. The most useful records were:

- `/Users/pierre/.codex/sessions/2026/08/01/rollout-2026-08-01T09-50-42-019fbd97-60c6-7e52-9180-b650a908c55c.jsonl`
- `/Users/pierre/.codex/sessions/2026/07/30/rollout-2026-07-30T08-30-57-019fb301-a6e7-79e2-8b57-b63bb66a49ce.jsonl`
- `/Users/pierre/.codex/sessions/2026/07/30/rollout-2026-07-30T08-30-53-019fb301-977b-77a2-b354-858d3a7918a5.jsonl`

The recovered notes reference:

- Palantir/Foundry-style ontology objects, links, and operational actions;
- `semantica-agi/semantica`, described in the earlier research as graph-native
  infrastructure for context and accountable AI systems;
- Semantica's context-graph / knowledge-graph / explainability and provenance
  framing;
- TypeGraph-style `BM25 + vectors + graph traversal` compiled into one SQL
  query with ontology reasoning at query time;
- Graphiti's temporal, provenance-bearing context graph and prescribed or
  learned ontology;
- LLM-driven ontology construction (the OntoEKG line of work); and
- a schema-first bootstrap idea: infer an initial ontology from raw database
  schemas before asking a model to add higher-level concepts.

The same CASS session also records the already-run corporate-eval plan,
canonical trajectory DAG, exact/lexical/dense retrieval, governed artifact
capsules, frontier proposal review, and the controlled shared-intent positive
control. Those are not counted as new architecture arms below.

## What is new versus already covered

| Idea | Current program coverage | Decision |
|---|---|---|
| Temporal provenance graph | Canonical trajectory DAG has causality and evidence refs, but no explicit typed object/link projection | **New projection arm** |
| Ontology objects and links | Existing typed metadata and scope filters, but no object identity/relationship layer | **New projection arm** |
| BM25 + vector + graph traversal in one query | Existing FTS/vector hybrid has no graph expansion | **New retrieval arm** |
| Ontology reasoning at query time | Existing retrieval uses scope and identifiers, not typed relation/path constraints | **New retrieval arm** |
| Operational actions and outcomes | Eval/memory proposals exist, but accepted/rejected/promoted/deprecated actions are not modeled as a graph | **New closed-loop arm** |
| Schema-first ontology bootstrap | Schema fingerprints exist; no measured schema-to-ontology extraction or drift test | **New extraction arm** |
| Learned ontology / LLM ontology construction | Frontier models draft proposals, but not a versioned ontology with contradiction and NIL handling | **New extraction arm, gated** |
| Graphiti temporal context graph | Prior runtime attempt was provider-unavailable; no fair graph-projection comparison | **Re-run as a representation comparison, not a product dependency** |
| Generic memory, dense retrieval, artifact reuse | Already tested with nulls and a controlled shared-intent positive control | **Do not repeat as an undifferentiated memory experiment** |

## Architecture to test

Keep the loss-aware trajectory DAG as the authority. Add projections in the
same disposable PostgreSQL instance so that the comparison changes one idea at
a time:

```text
native trajectory DAG
  -> typed object/link projection
  -> temporal/provenance edge table
  -> authorized relational query
       (FTS + vector candidates + graph expansion)
  -> optional frontier adjudication
  -> auditable action/outcome record
```

The minimum objects are `user`, `tenant`, `team`, `task`, `trace`, `span`,
`system`, `tool`, `schema`, `artifact`, `eval`, `failure`, `skill_candidate`,
`memory_candidate`, `action`, and `outcome`. Every edge carries source trace
IDs, validity interval, policy/epoch snapshot, extractor version, and an
explicit `asserted`, `inferred`, `contradicted`, or `nil` status.

Do **not** add Neo4j, a hosted ontology service, or a second search system for
this test. PostgreSQL tables, recursive CTEs, FTS, pgvector, and JSONB are
enough to measure whether the representation helps. A graph database becomes
relevant only if graph expansion is the measured bottleneck.

## Empirical matrix

Use the existing shared-intent artifact cohort, natural recovery/eval
proposals, and a held-out schema/tool-drift cohort. Freeze candidate generation
before labels are opened.

| Arm | Representation | Retrieval/action behavior |
|---|---|---|
| A0 | Canonical DAG + current exact/lexical/dense lanes | Baseline |
| A1 | Typed objects only | Filter and aggregate by object identity; no graph expansion |
| A2 | Temporal/provenance graph only | Path and neighborhood retrieval; no vectors |
| A3 | Objects + graph + FTS | Identifier-first graph retrieval |
| A4 | Objects + graph + FTS + pgvector | TypeGraph-style hybrid candidate recall |
| A5 | A4 + query-time ontology constraints | Require typed paths such as task→schema→artifact→outcome |
| A6 | A5 + action/outcome loop | Propose, approve, replay, promote, deprecate, and measure the action |
| A7 | Schema-first ontology bootstrap | Infer objects/relations from schemas, then replay |
| A8 | Schema-first + frontier ontology refinement | Model may add concepts, aliases, contradictions, or NIL; all gated |

## Questions and acceptance gates

The test must answer the questions the current retrieval study cannot:

1. Does a typed graph improve cross-user task-cluster precision without
   leaking unauthorized nodes?
2. Does a temporal edge prevent stale artifact, schema, or memory reuse better
   than a flat vector/FTS row?
3. Does graph expansion recover a known shared-intent artifact when the flat
   library contains the components but not the whole query?
4. Does an action/outcome graph distinguish a proposed insight from a validated
   intervention and produce a lower false-promotion rate?
5. Does schema-first ontology bootstrapping improve alias/NIL recall on held-out
   systems without increasing wrong-system links?
6. Does query-time ontology reasoning reduce frontier calls or merely add
   latency and false confidence?

Required metrics:

- task/artifact/eval retrieval Recall@1/3/10 and MRR;
- alias, NIL, wrong-system, and contradiction precision/recall;
- temporal-drift and stale-reuse false-accept rate;
- semantic execution correctness and unsafe-action rate;
- unauthorized-node and unauthorized-edge count (must be zero);
- proposal precision, action acceptance, rollback/deprecation correctness;
- frontier calls, latency, tokens, and storage/index cost;
- evidence coverage and independent-verifier agreement.

Promotion requires a paired lift over A0 on a sealed holdout. A graph that only
improves explainability or recall but increases stale or unauthorized accepts
does not promote. A typed graph with no utility remains a projection for
debugging and provenance, not a new production subsystem.

## Expected outcome and boundary

The Palantir/Semantica ideas add a missing **semantic operating layer** between
raw trajectories and retrieval: typed entities, relations, time, provenance,
and actions. They do not replace exact identifiers, execution verification,
or the canonical evidence DAG. They also do not establish that a knowledge
graph will solve enterprise skill mining; that remains an empirical question.

The most likely useful result is a small relational projection that improves
cross-trace aggregation, stale/contradiction handling, and auditability while
leaving vectors as optional candidate recall. The most likely failure mode is
ontology hallucination or graph over-linking: a plausible relationship can
look authoritative unless every edge remains evidence-linked and NIL/unclear
are first-class values.

## Additional tool candidates from the term-extraction article

The linked enterprise RAG term-extraction research adds a separate vocabulary
layer to test, not a replacement for the graph arm. The highest-value tools are
TermoUD/Termolator (interpretable termhood baseline), GLiNER (typed span
challenger), TermSuite (variant/alias clustering), acronym expansion with
explicit NIL outcomes, and SEQUER-style original-to-reformulated query mining.
QueryGym and ConvGQR are useful second-stage query-expansion challengers;
SIRA-style enrichment is a search-only projection. DataTrove, NeMo Curator,
Dolma, and Data-Juicer are scale substrates and should not be mistaken for
relevance methods.

The complete ablation and promotion gates are in
[`term-extraction-retrieval-enrichment-2026-08-04.md`](../protocols/term-extraction-retrieval-enrichment-2026-08-04.md).
The key combined test is `baseline -> approved terms -> aliases ->
reformulation -> ontology edges`, with exact identifiers, source evidence,
authorization, and temporal validity held constant.
