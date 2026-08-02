# Corporate ontology extraction and fine-tuning: reality check

Date: 2026-08-02  
Status: evidence review and experiment design; no automatic ontology promotion

## Executive answer

Your real-world result is not surprising: **automatic enterprise ontology
induction from one tool, one trace, or an uncurated log corpus is still an
unsolved problem**. The marketing claim usually collapses at least five
different tasks into the word “ontology”:

1. extracting terms and entities;
2. resolving aliases to the same real-world entity;
3. proposing classes and relations;
4. grounding facts in a formal schema with constraints; and
5. learning the decisions, actions, authority, and temporal state of a business.

The tools we found are better than a one-pass prompt when used for the specific
subproblem they were designed for. None of them turns raw corporate traces into
a trustworthy, executable ontology without a corpus, evidence links, negative
examples, version/authority metadata, and human or outcome-based validation.

## Why a single-tool ontology is underdetermined

A tool call exposes an interface projection: names, parameters, and perhaps an
output. It does not identify the business meaning of those fields. The same
`search`, `query`, or `create` tool can represent different systems, roles,
time periods, or authorization scopes. Many incompatible ontologies can explain
the same call. A model forced to choose one will fill the missing structure with
plausible defaults, which looks coherent but is often wrong.

Corporate traces add four difficult ambiguities:

- **polysemy:** a nickname can name different systems or teams;
- **identity:** two surface forms may be one object, or one surface form may be
  several objects;
- **time:** the same entity, schema, or policy changes between runs;
- **authority:** a fact can be true but not usable by this user or agent.

An ontology extractor that does not model these explicitly cannot be evaluated
by fluency or graph density. It needs evidence-level precision, NIL/unknown
behavior, temporal validity, and downstream task outcomes.

## What the candidate tools actually do

| Tool or method | What it is genuinely good at | Why it did not solve our raw-corporate-data problem |
| --- | --- | --- |
| [OntoEKG](https://arxiv.org/abs/2602.01276) | Closest recent work to ontology induction: separates class/property extraction from hierarchy/entailment and serializes RDF. | Its reported Data-domain fuzzy F1 is `0.724`, and the abstract explicitly reports limitations in scope definition and hierarchical reasoning. It is a proposal generator, not a correctness oracle. |
| [Microsoft GraphRAG](https://github.com/microsoft/graphrag) | Extracts entities, relationships, claims, communities, and summaries to improve corpus-level retrieval. | It creates a graph-shaped index, not a validated enterprise ontology. Microsoft warns indexing is expensive, says out-of-box prompts may need tuning, and describes the repository as a methodology/demo rather than a supported product. |
| [OntoGPT/SPIRES](https://github.com/monarch-initiative/ontogpt) | High-quality schema-guided extraction and ontology grounding when a target ontology already exists. | It assumes the ontology/template. It is excellent for populating a known model, not discovering the right corporate model from scratch. |
| [Text2KGBench](https://arxiv.org/abs/2308.02357) | A proper evaluation framing: fact extraction, ontology conformance, and hallucination metrics over an input ontology. | It evaluates extraction under a provided ontology; it does not test ontology discovery, enterprise identity, authority, or changing systems. |
| [Zingg](https://www.zingg.ai/product/entity-resolution-platform) | Entity resolution with blocking, labeled match/non-match pairs, active learning, persistent IDs, and incremental merge/split behavior. | This is one of the missing pieces for corporate aliases, but it resolves entities; it does not decide which relations, actions, or business rules belong in the ontology. |
| Neo4j [LLM Graph Builder](https://neo4j.com/developer/genai-ecosystem/llm-graph-builder/) | Practical extraction of lexical/document and entity graphs with vector/full-text/hybrid retrieval. | It makes graph construction easier; it does not make extracted edges true, current, authorized, or useful for a changed-system action. |
| TermSuite/AcronymExpansion ports | Deterministic termhood, variants, acronym candidates, and conservative NIL queues. | Our receipts show candidate generation and retrieval diagnostics, not semantic alias truth or ontology quality. |
| Graphiti/LangMem-style memory | Temporal facts, provenance, contradiction handling, and conversation-derived memory candidates. | They preserve changing facts; they do not automatically discover a correct enterprise schema or validate actions. |
| [SHACL](https://www.w3.org/TR/shacl12-core/) | Formal graph-shape constraints and machine-readable validation reports. | Validation catches violations after a shape exists. It cannot decide whether the shape or relation was semantically correct. |
| [EnterpriseRAG-Bench](https://github.com/onyx-dot-app/EnterpriseRAG-Bench) | A large synthetic document corpus and hard retrieval slices. | It has no real user trajectories, tool outcomes, authority epochs, or skill interventions. It is a document-side fixture only. |

The closest missing capability is therefore not “another ontology generator.” It
is a **governed entity-and-schema learning loop** combining entity resolution,
schema-guided extraction, hard-negative mining, formal validation, and replay.

## Is it legitimately unsolved?

Yes, in the strong form implied by the social posts: *raw corporate traces in →
correct ontology out, with no review or labels*. That is not established by the
current literature or tools. The recent OntoEKG result is useful precisely
because it quantifies a gap rather than claiming perfection. Existing systems
are much more mature in the following restricted forms:

- **known schema population:** extract fields/relations into a supplied
  LinkML/RDF/JSON schema;
- **entity resolution:** learn whether records refer to the same object from
  labeled pairs and active-learning queries;
- **retrieval graphing:** add graph structure to improve multi-hop or global
  retrieval;
- **constraint checking:** reject malformed or impossible graph instances;
- **task adaptation:** fine-tune a model for a narrow, labeled task with a
  frozen holdout.

The hard unsolved part is the join: deciding which extracted concept is the
same enterprise object, which relation is authoritative and current, what the
agent was allowed to see, and whether using the proposed object improves a
real task.

## What companies are actually doing

Public evidence points to a layered strategy, not “train on every log.”

### Palantir: model the operating world, not just text

Palantir’s [Ontology](https://www.palantir.com/platforms/ontology/) explicitly
models enterprise **data, logic, actions, and security**. Its documentation
describes object/link/property models, actions that write to operational
systems, decision lineage, and granular controls. This is a large, curated
semantic/operational layer with continuous synchronization—not a one-shot LLM
ontology pass. It is the clearest production precedent for the architecture we
need to emulate: meaning is tied to actions, authority, and lineage.

### Microsoft: GraphRAG plus prompt/index tuning

Microsoft’s open [GraphRAG](https://microsoft.github.io/graphrag/) extracts a
graph and hierarchical community summaries, then provides local/global/DRIFT
retrieval. The project warns that indexing is expensive and recommends prompt
tuning. This is a retrieval architecture; it does not claim that the generated
graph is the organization’s canonical ontology.

### ServiceNow: focused data, instruction tuning, evaluation, monitoring

ServiceNow’s June 2026 responsible-AI white paper describes a lifecycle of
research, development, validation, deployment, monitoring, and retirement. It
says it fine-tunes on **constrained, focused ServiceNow datasets**, applies
instruction fine-tuning for target personas, publishes model cards, collects
usage/feedback metrics, and runs standard benchmarks before deployment. It
also says customer data is opt-in and filtered/anonymized when contributed.
This is the opposite of indiscriminate training on raw customer traces.

### Salesforce: synthetic environments and genuinely large matched data

Salesforce’s [synthetic-enterprise-data work](https://www.salesforce.com/news/stories/synthetic-data-in-enterprise-ai/)
uses business-logic-grounded synthetic records and agent tasks to train and
benchmark safely. Its [CloudOps fine-tuning report](https://www.salesforce.com/blog/time-series-models-business-data/)
is a useful example of when fine-tuning really works: 80+ metrics, 2M+ entities,
1.3B+ time steps, holdouts for upcoming migrations/new services, baseline
comparisons, and drift-aware integration. The reported gains are for time-series
forecasting, not ontology extraction, but the data-scale and holdout discipline
are directly relevant.

### Morgan Stanley: eval-driven retrieval before model retraining

OpenAI’s [Morgan Stanley case study](https://openai.com/index/morgan-stanley/)
describes expert-graded summarization and translation evals, daily regression
testing, advisor feedback, and iterative retrieval improvements over a
100,000-document corpus. This is a strong real enterprise precedent for
learning from usage without claiming that raw chat logs should be baked into
model weights.

### Bloomberg: the exceptional vertical-pretraining case

[BloombergGPT](https://arxiv.org/abs/2303.17564) is a 50B-parameter finance
model trained on very large, curated financial and general corpora. It proves
that vertical pretraining can work when a company has massive, coherent domain
data and a research organization. It is not a realistic template for most
companies with months of agent logs, and it does not solve per-company aliases,
authority, or action validity.

### Cloud model vendors: fine-tuning is a narrow adaptation lever

AWS, Databricks, and Cohere all expose private fine-tuning or embedding
customization ([AWS guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/retrieval-augmented-generation-options/rag-vs-fine-tuning.html),
[Databricks guidance](https://community.databricks.com/t5/technical-blog/getting-started-with-fine-tuning-on-databricks/ba-p/96923),
[Cohere embedding guidance](https://cohere.com/blog/embedding-models)). Their
common guidance is consistent: use RAG for frequently changing facts and
fine-tuning for behavior, terminology, style, extraction, or output format when
high-quality labeled data exists. Fine-tuning is not a replacement for a live
source of truth or governance.

## What this means for Frankengate

The architecture should not contain a “generate ontology from traces” button.
It should expose a staged pipeline with explicit object types:

```text
raw trace/tool event
  -> deterministic identifiers, schemas, parameters, timestamps
  -> candidate term/alias/entity mentions
  -> active-learning entity resolution (match / non-match / NIL / unsure)
  -> frontier extraction into a versioned typed schema
  -> SHACL-like conformance and evidence checks
  -> temporal/authority/lineage graph projection
  -> retrieval and artifact/skill proposals
  -> independent changed-system replay
```

The initial persisted representation can remain PostgreSQL tables + JSONB +
pgvector. A graph projection is useful for traversal and visualization, but a
separate graph database is not justified until graph queries improve a measured
task. The ontology should be a versioned, reviewable projection—not the raw
trace store and not model weights.

## Fair empirical test

We should test the claim directly, with one frozen corpus and identical labels:

### Corpus and labels

- EnterpriseRAG-Bench for document-side cross-source and conflict slices.
- Authorized trace/tool samples with typed schemas, exposure states, outcomes,
  scope IDs, and authority/schema epochs.
- Synthetic same-surface/wrong-system, stale-version, and NIL cases generated
  from known schemas.
- Frontier-adjudicated labels for entity identity, alias, relation, scope,
  temporal status, action compatibility, and “insufficient evidence.”

### Independent arms

1. One-pass frontier “discover the ontology.”
2. Termhood/acronym + deterministic schema mining.
3. GraphRAG extraction/community summaries.
4. OntoGPT/SPIRES with a fixed starter schema.
5. OntoEKG or a faithful reimplementation of its extract/entail split.
6. Deterministic candidates + Zingg/Splink-style active entity resolution.
7. Hybrid: (6) → schema-guided frontier extraction → SHACL/evidence checks.

Then test adaptation separately:

- no tuning + retrieval;
- RAG-only;
- LoRA/SFT on reviewed extraction examples;
- contrastive embedding tuning on reviewed positives and hard negatives;
- hybrid tuned retriever + schema-guided extraction + replay.

### Splits and metrics

Hold out projects, systems, users, and time. Never let an alias or artifact leak
across those boundaries. Report:

- entity/alias precision, recall, F1, and B-cubed cluster quality;
- relation evidence precision and ontology/schema conformance;
- hallucinated facts and unsupported edges;
- NIL/abstention and “unsure” calibration;
- collision-before-target and wrong-system rate;
- temporal/authority correctness and metadata leakage;
- retrieval MRR/Recall and answer completeness;
- independent tool/SQL replay success and semantic result correctness;
- user correction burden, latency, and cost.

The decisive result is not graph quality alone. A method wins only if its
proposals improve held-out retrieval **and** changed-system replay without
increasing unauthorized or wrong-system actions.

## Decision

The tools we already found are not obviously “bad”; most were asked to solve a
larger problem than they claim to solve. OntoEKG is the most relevant missing
ontology-induction baseline. OntoGPT, GraphRAG, Zingg, Text2KGBench, and SHACL
should be combined as specialized stages, not compared as interchangeable
one-click generators.

The genuinely novel and useful Frankengate contribution remains the conjunction
of:

1. trajectory-derived concepts and artifacts;
2. active-learning entity/alias resolution;
3. hard negatives and identifier-aware representations;
4. temporal, authority, and evidence provenance;
5. executable validation and changed-system replay; and
6. outcome-backed skill or embedding adaptation.

That is a credible research gap. “Generate a correct corporate ontology from a
single tool” is not currently a solved product category.
