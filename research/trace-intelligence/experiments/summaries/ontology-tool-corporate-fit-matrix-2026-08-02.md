# Ontology-tool corporate-fit matrix

**Date:** 2026-08-02  
**Status:** evidence synthesis; no automatic ontology-promotion claim

## Executive conclusion

The “one tool produces the corporate ontology” claim is not supported. The
tools are useful, but they solve different subproblems:

```text
mentions and identifiers
  -> typed schema proposal
  -> constrained population
  -> identity / alias / NIL decision
  -> temporal and authority validation
  -> replay and outcome measurement
```

The missing part is not simply a stronger generator. A raw corporate corpus
does not identify canonical identity, user intent, temporal validity, or
whether a relation is operationally safe. Those require labels, provenance,
scope, and an executable check.

## Fit by method

| Method | What it is good at | What our evidence says | Frankengate disposition |
|---|---|---|---|
| Deterministic schema/identifier mining | Exact names, columns, tools, endpoints, scopes | Strongest retrieval signal; structured source filtering improved full EnterpriseRAG MRR `.511→.594` and eliminated wrong-source extras, but same-source distractors remained | **Ship as first stage** |
| GOI-style typed proposal | Drafting entities, dimensions, relations, constraints | Five-case frontier probe returned valid output `5/5`; output was unstable across repeats (`14.2→10.2` entities) and had no identity or temporal labels | **Schema-draft queue only** |
| OntoGPT/SPIRES-style population | Filling a reviewed ontology or LinkML template with evidence | Fewer, more stable outputs than free-form proposal; starter-schema grounding was not consistently better (`.781` versus GOI `.952` on the primary five-case run) | **Populate reviewed schemas only** |
| GLiNER / Termolator / TermSuite-style term mining | Candidate terms, spans, variants, acronyms | Corrected contextual GLiNER probe reached `7/8`; termhood transferred poorly to unseen schemas (`.015` direct recall); frequency-derived aliases covered only `.065` of targets and had 506 ambiguous surfaces | **Review/search enrichment only** |
| GraphRAG / Graphiti-style graph expansion | Provenance-aware neighborhood traversal and temporal facts | Graph density is not truth; expansion can amplify wrong-system, stale, or unauthorized edges | **Optional retrieval view behind gates** |
| Generic embeddings | Broad candidate recall and paraphrase matching | MiniLM semantic R@20 was `.12` on EnterpriseRAG, below lexical candidate recall `.224`; no corporate embedding promotion | **Candidate recall only** |
| Labelled adapter/reranker | Compressing reviewed domain-specific relevance signals | A task-disjoint Nomic adapter improved MRR `.940→.948` and R@1 `.909→.932`, but lowered R@5 and did not reduce incompatible candidates | **Shadow model with rollback** |
| Frontier model/judge | Ambiguous candidate review, relation proposal, synthesis | Luna improved semantic reranking MRR `.114→.195`, but could not recover candidates outside the lexical pool; silver ontology judgments are not precision labels | **Selective review only** |
| Replay/authority verifier | Operational truth: compatibility, safety, changed-system behavior | Typed metadata plus deterministic gates produced `10/10` safe/correct SQLite replays; naive name-first reuse produced seven unsafe accepts | **Authoritative promotion gate** |

## Why single-tool ontology extraction fails on corporate data

The hard cases are not ordinary concept extraction:

1. **Same surface, different system:** `orders`, `customer`, or an acronym can
   refer to unrelated systems.
2. **Temporal replacement:** an old table, API, or dashboard can remain
   textually similar after it is retired.
3. **Scope and authority:** a semantically plausible edge may be outside the
   requesting team’s entitlement or epoch.
4. **NIL and ambiguity:** the correct result can be “not enough evidence”; the
   EnterpriseRAG targetless slice returned candidates for all 30 questions.
5. **Operational semantics:** two queries can return similar rows while one is
   unsafe, stale, or wrong-grain.
6. **Intent is latent:** a prompt or tool description rarely states whether a
   user wants a reusable artifact, a one-off answer, a migration, or a
   diagnosis.

Graph density, evidence substring overlap, JSON validity, and embedding
similarity do not resolve these cases. They are useful intermediate signals,
not truth criteria.

## What companies appear to do

Public enterprise practice converges on a staged loop rather than raw-log
pretraining:

```text
metadata / hybrid retrieval baseline
  -> reviewed query–document examples and hard negatives
  -> task-specific reranker or embedding tune
  -> held-out evaluation and human review
  -> versioned deployment, monitoring, and rollback
```

Databricks emphasizes metadata, synonyms, joins, verified queries, and
diagnosing retrieval before embedding tuning. Google’s embedding-tuning
workflow requires query/corpus relevance examples. Cohere’s reranker training
uses positives and hard negatives. AWS separates corpus/index updates from
versioned model deployment. None of these public practices demonstrates that
unlabelled employee logs can be converted directly into a canonical ontology.

The corporate adaptation is therefore to mine traces into *supervision*:
successful artifacts, rejected candidates, exposed-but-unused alternatives,
same-surface collisions, temporal replacements, authority conflicts, and
explicit NIL/unclear cases. The raw trace is evidence, not a training label.

## Smallest defensible architecture

```text
typed trace + scope + authority + exact identifiers
  -> lexical / term / dense candidate pool
  -> optional labelled reranker
  -> selective frontier or human review
  -> identity, temporal, authority, and NIL checks
  -> independent execution/replay
  -> versioned alias, artifact, eval, or skill proposal
```

Only the final replayed and reviewed object can become reusable knowledge.
Ontology generation should remain a versioned review queue. The graph, memory,
embedding, and skill stores should consume approved projections, never write
directly from a model response.

## Decisive next experiment

The current ontology matrix is promotion-blocked because it lacks a consented
semantic cohort. The minimum useful study is:

- 100 entity/alias targets, 50 hard negatives, and 25 NIL/unclear cases;
- two independent labels plus adjudication;
- principal, team, project, source-system, and effective-time holdouts;
- same-surface/wrong-system, temporal replacement, stale-authority, and
  changed-tool-contract strata;
- arms: deterministic schema terms, GOI proposal, OntoGPT population,
  GraphRAG extraction, and the staged governed pipeline;
- metrics: alias F1, relation evidence precision, NIL abstention, temporal and
  authority accuracy, replay success, reviewer correction burden, latency, and
  cost.

Until that cohort exists, a new ontology generator or vector database is not
the bottleneck. The bottleneck is independent identity and outcome evidence.

## Evidence links

- [EnterpriseRAG-Bench full source-filter ceiling](enterprise-rag-source-filter-ceiling-full-2026-08-10.md)
- [Frontier ontology-induction proxy](ontology-induction-frontier-proxy-2026-08-02.md)
- [Ontology-induction prior-art refresh](ontology-induction-prior-art-refresh-2026-08-02.md)
- [Corporate trace-artifact learning reality check](reality-check-2026-08-10.md)
- [Ontology induction matrix](../../configs/studies/ontology-induction-matrix-v1.json)
- [Company fine-tuning practice map](company-finetuning-practice-map-2026-08-02.md)

