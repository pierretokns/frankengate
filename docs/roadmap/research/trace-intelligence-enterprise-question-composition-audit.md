# Trace Intelligence Composition Audit for Enterprise Questions

**Status:** architecture decision record and feasibility gate

**Date:** 2026-07-30

**Scope:** Frankengate personal history, trace mining, eval creation, memory,
skills, recommendations, team learning, enterprise learning, retrieval, and
model adaptation

## Verdict

The earlier work chose a sensible storage boundary, but it did **not** prove that
the combined system could answer the intended enterprise questions. This audit
closes that gap.

The corrected verdict is:

1. **Keep Aurora PostgreSQL as the only required authority and query system.**
   Several hundred GB does not justify another persistent analytics, vector, or
   graph system. The difficult work is evidence modeling, labels, authorization,
   causal validation, and product policy—not vector throughput.
2. **Do not claim the current implementation already solves the problem.** The
   current analytics migration stores experiments, runs, results, artifacts, jobs,
   and attempts with tenant-only RLS. The current `Trace` is a span tree. Neither
   is yet the canonical, subject-scoped, branch-preserving, outcome-linked evidence
   model required for the enterprise questions.
3. **Combine concepts, not upstream products.** AgentRx, Signals, AgentEvals,
   Phoenix, Opik, Langfuse, OpenRCA, Graphiti, LangMem, MemInsight, Dreams,
   ReasoningBank, LEGOMem, ACE, Memento-Skills, MemRL, CASS-like retrieval, and
   import tools contribute useful mechanisms. They fit as native relational
   records, jobs, and release workflows inside Frankengate. They do not fit as a
   pile of separately deployed authorities.
4. **Embeddings are a secondary candidate generator, not the foundation of the
   product.** Exact fields, ordered trajectory features, PostgreSQL full-text
   search, outcome labels, and organization-specific ontologies answer many of
   the highest-value questions more reliably. A custom embedding model is
   conditional on a frozen enterprise benchmark proving that hybrid retrieval
   with a strong general model still fails.
5. **The most ambitious questions are not direct search questions.** “Who does
   similar work?” is a retrieval and privacy problem. “What skill is missing?”
   is an attribution problem. “What intervention will help?” is a causal
   experiment. “What should become memory or model weights?” is a governed
   promotion decision. Treating all four as semantic search would fail.

The architecture is therefore **viable but incomplete**. Build the evidence and
measurement kernel first. Kill or narrow the product if task boundaries,
verified outcomes, privacy-safe aggregation, or useful repeated patterns cannot
be established on real traces.

## Empirical checkpoint: 2026-07-30

Two new experiments narrow the architecture without changing the claim
boundary:

1. A frozen 145-document, 99-query
   [CodeTraceBench](https://huggingface.co/datasets/NJU-LINK/CodeTraceBench)
   silver-label factorial compared exact, structured, lexical, and pinned
   [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
   retrieval. Structured plus dense reached `0.8182` Recall@20 versus `0.7323`
   for exact-only; the paired bootstrap 95% interval for the `+0.0859` lift was
   `[0.0354, 0.1364]`. Dense alone added only `0.0051`, and the tested lexical
   fusion regressed exact-identifier recall. This supports sparse task-level
   general embeddings only after exact and structured signals. It does not
   justify a custom embedding model.
2. The same 145 documents and pinned 1,024-dimensional vectors were loaded into
   one disposable PostgreSQL 16 plus pgvector table behind forced RLS. All
   missing/stale-epoch, wrong-subject, wrong-tenant, and wrong-purpose candidate
   counts were zero before ranking; withdrawn and deleted rows disappeared; and
   rollback left zero rows. Exact pgvector achieved `0.6667` Recall@20 at
   `3.017 ms` local sequential p50. The tested FTS/trigram/vector RRF improved
   Recall@20 by only `0.0051`, reduced nDCG and MRR, and cost `256.843 ms` p50,
   almost entirely because of the trigram lane. That hybrid is rejected for this
   workload. The run is a correctness result, not Aurora, concurrency, or scale
   evidence.
3. A pinned two-session
   [Trace Commons](https://huggingface.co/datasets/trace-commons/agent-traces)
   cohort preserved 1,602 native records, all 1,266 parent edges, and all eight
   context-artifact call/result joins. It reconstructed one exact
   write-to-later-read continuity and two edits, and emitted an
   interval-censored gap instead of inventing a missing revision. All temporal
   and imported-scope negative controls passed. This proves a loss-aware
   versioned-context import primitive, not that the memory was correct, helpful,
   or causally responsible for later work.

The smallest justified system is therefore still one governed PostgreSQL/Aurora
authority plus asynchronous workers and conditional protected object bytes.
Use exact and structured lanes on every eligible query; invoke general dense
retrieval only for task-similarity questions where the benchmark supports it.
Do not ship the tested trigram-heavy fusion, a custom embedding, another vector
database, or automatic memory promotion. CMU access is explicitly waived:
public pinned cohorts are sufficient for the current gates, and CMU is not on
the critical path.

## What the current code proves—and does not prove

The existing implementation is useful substrate:

- `core/schemas/trace.go` captures request/trace IDs, parent/child spans, span
  kinds, events, model attributes, retries, fallbacks, and MCP tool attributes.
- `analytics-rs/migrations/001_analytics_contract.sql` has immutable experiment
  intent, run and evaluator revisions, durable jobs and attempts, and forced RLS.
- `analytics-rs/src/database.rs` installs tenant state transaction-locally.

It does not yet prove the target product:

- The trace model is a tree, while imported chats and agents can branch, retry,
  resume, delegate, propose tools without executing them, or produce side effects
  not established by a tool response.
- The analytics schema is tenant-scoped, not subject/team/project/case/purpose/
  classification/authorization-epoch scoped.
- There are no canonical task attempts, task signatures, external outcome
  observations, skill hypotheses, temporal facts, memory releases, intervention
  exposures, correction appeals, or privacy-safe aggregate releases.
- The current S3 hybrid log path intentionally tolerates failed uploads. It cannot
  hold canonical evidence until a durable outbox, receipt, reconciliation, and
  deletion protocol exists.

The database choice survives. The evidence model needs a material revision.

## The minimal composable system

```text
native/imported trace
  -> loss-aware canonical event DAG
  -> current authorization + classification + purpose gate
  -> deterministic features and cheap signals
  -> task/attempt segmentation and independently observed outcomes
  -> exact / structured / lexical candidate retrieval
  -> optional sparse task-level embeddings and reranking
  -> evidence-backed hypotheses and calibrated abstention
  -> reviewed eval, memory, skill, or intervention proposal
  -> shadow / replay / canary / randomized validation
  -> scoped immutable release with rollback and deletion lineage
```

Aurora owns every authoritative node in that flow. Existing asynchronous Rust
workers can calculate derived features, embeddings, clusters, judge outputs, and
aggregate releases. S3 is optional for large immutable payload bytes only; every
object must be addressed by an authorized Aurora manifest.

This is one operational system plus existing worker compute—not an
observability platform, graph database, vector database, and memory service.

## How the source systems actually compose

| Concept family | Sources | What composes into Frankengate | What must not be imported |
|---|---|---|---|
| Canonical trajectories | [OpenInference](https://github.com/Arize-ai/openinference), [AgentRx](https://github.com/microsoft/AgentRx), provider-neutral importers | Loss-aware event DAG; typed model, tool, authorization, retry, fallback, delegation, observation, and outcome nodes; adapter revision and loss receipt | OTel span trees as the sole canonical representation; importer linearization that silently discards branches or hidden/tool events |
| Cheap trace selection | [Signals](https://arxiv.org/abs/2604.00356) | Versioned rephrase, stagnation, loop, failure, disengagement, cost, latency, and environment detectors over every trace; random audit sample | Treating a selector as a failure, intent, or skill label |
| Failure localization | [AgentRx](https://github.com/microsoft/AgentRx) | Declarative invariants, violation evidence, decisive-step hypothesis, failure taxonomy, abstention | Generated unrestricted checker execution; “root cause” from proximity or an LLM judge |
| Multimodal diagnosis | [OpenRCA](https://github.com/microsoft/OpenRCA) | Keep trace topology, logs, metrics, deployment events, policy state, and external outcomes separate; join by IDs, time, and topology | Flattening every modality into text or a single embedding |
| Retrospective evals | [AgentEvals](https://github.com/agentevals-dev/agentevals) | Exact, ordered, unordered, semantic, invariant, and custom assertions over stored trajectories | Claiming a stored trace proves behavior after a system change or proves an external side effect |
| Dataset/experiment lifecycle | [Phoenix](https://github.com/Arize-ai/phoenix), [Opik](https://github.com/comet-ml/opik), [Langfuse](https://github.com/langfuse/langfuse) | Annotated example -> immutable dataset revision -> experiment -> calibrated result -> release decision; feedback target and evaluator revision | Deploying all three platforms; letting any become a second tenant, deletion, or dataset authority |
| Exact-first history search | CASS concepts, [claude-history](https://github.com/raine/claude-history), [Prompt-Scope](https://github.com/monapdx/Prompt-Scope) | Field-aware exact/lexical/fuzzy/semantic retrieval, quoted identifiers, compact evidence previews, private personal reflection, resumable analysis | Assuming a local single-user index proves RLS, deletion, or enterprise completeness |
| Temporal facts | [Graphiti](https://github.com/getzep/graphiti), [MemInsight](https://github.com/amazon-science/MemInsight) | Source-cited entity/fact/episode records, valid-time and system-time, contradiction and supersession, typed attributes | A graph backend at launch; name-similarity entity merging; graph proximity as authorization |
| Memory extraction | [LangMem](https://github.com/langchain-ai/langmem), [Anthropic Dreams](https://platform.claude.com/docs/en/managed-agents/dreams) | Candidate extraction into a separate immutable release; preview, diff, edit, reject, expire, promote, rollback | Automatic write into live memory, in-place `MEMORY.md` mutation, or “latest statement wins” |
| Procedural memory | [ReasoningBank](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/), [LEGOMem](https://www.microsoft.com/en-us/research/publication/legomem-modular-procedural-memory-for-multi-agent-llm-systems-for-workflow-automation/), [ACE](https://www.microsoft.com/en-us/research/publication/agentic-context-engineering-evolving-contexts-for-self-improving-language-models/) | Separate orchestration and execution playbooks; successful/failed contrasts; compact versioned deltas; held-out eval and rollback | Self-judge auto-promotion, unbounded prompt mutation, or organizational policy authored by an untrusted agent |
| Utility-aware routing | Memento-Skills and MemRL research patterns | Retrieve semantically plausible candidates, then rank by measured task-specific utility; retain no-memory/no-skill baselines | Treating downstream success as clean credit for one retrieved memory/skill; stationary-task assumptions in a changing enterprise |
| Eval generation and repair | [Anthropic Bloom](https://www.anthropic.com/research/bloom), [OpenAI self-improving tax agents](https://openai.com/index/building-self-improving-tax-agents-with-codex/) | Reviewed behavior -> varied candidate cases; expert correction -> structured finding -> targeted eval -> bounded change | Synthetic prevalence claims, production credentials in simulators, or assuming every human edit is an error correction |

All twelve concept families can coexist in one native design. They are not twelve
services. The incompatibilities are about authority and claims, not data types.

## What works together well

### Canonical DAG + deterministic signals + exact-first retrieval

This is the strongest launch combination. A canonical DAG preserves what happened;
cheap signals select noteworthy attempts; exact/structured/lexical queries find
identifiers, tools, errors, routes, files, sources, and ordered recovery deltas.
None of these needs an embedding or an LLM judge.

### Task signatures + optional embeddings + human-confirmed similarity

Represent a task as several dimensions rather than one vector:

- objective and requested artifact;
- entities and exact identifiers;
- tool and source families;
- environment, repository, cloud service, permissions, and constraints;
- ordered action/recovery signature;
- verified terminal outcome.

Use SQL filters and lexical retrieval first, then embeddings to generate candidates
for semantic dimensions. Rerank with structured compatibility and show cited
exemplars. A user correction updates the task label; vector distance never becomes
the label.

### Diagnosis hypotheses + eval promotion

AgentRx-style invariants and OpenRCA-style modality joins can nominate the earliest
preventable step and alternative explanations. A real trace can then become an
AgentEvals-style regression fixture. This works well if the product distinguishes:

1. deterministic invariant violation;
2. likely contributing step;
3. experimentally supported cause.

### Temporal facts + proposal-only memory

Graphiti and MemInsight concepts combine well with Dreams and LangMem when facts
remain source-cited, bitemporal proposals. Relational fact and edge tables are enough
initially. Memory releases can render to harness destinations such as `MEMORY.md`,
project instructions, a personal prompt, or a skill file only after approval. The
rendered file is a destination artifact, not the authority.

### Procedural playbooks + evals + controlled interventions

ReasoningBank, LEGOMem, ACE, and Memento-style skill evolution become useful when a
playbook has a trigger, preconditions, required permissions/tools, steps, negative
cases, verifier, owner, source traces, scope, expiry, and rollback. Its utility is
measured against no-skill and current-skill controls. This is safer and more
reversible than model fine-tuning.

## Hard edges and combinations that do not work

### OTel alone does not preserve the enterprise evidence

OTel and GenAI semantic conventions are valuable interchange and export formats,
including tool-call semantics, but a parent/child span tree does not necessarily
preserve conversation branches, competing attempts, joins, resumptions, tool
proposal versus authorization versus execution, or independent side effects. The
canonical representation must be a DAG, with OTel as one projection. The
[OpenTelemetry GenAI conventions](https://github.com/open-telemetry/semantic-conventions)
also keep sensitive prompt/tool content opt-in and continue to evolve, so schema
revisions and content-loss manifests are mandatory.

### Signals + embeddings do not diagnose skill

Repeated rephrasing, loops, semantic clusters, and eventual success can show a
recurring symptom. They cannot distinguish:

- missing user knowledge;
- missing or stale documentation;
- missing permission;
- unavailable or poorly described tool;
- provider/model limitation;
- routing or retrieval failure;
- policy/governance denial;
- incident, latency, quota, or environment failure;
- deliberate exploration.

A “cloud skill gap” is therefore a **contestable intervention hypothesis**, not a
person attribute. It needs a task-to-capability ontology, evidence that the task
required the capability, elimination of environment alternatives, a verified
outcome, and ideally evidence that the proposed learning resource changes later
performance.

### Phoenix + Opik + Langfuse is duplication, not composition

Their useful lifecycle concepts overlap. Operating them together would duplicate
trace ingestion, identity, retention, dataset membership, evaluator state,
annotations, exports, and incident response. Langfuse’s self-hosted architecture,
for example, includes multiple stateful components; it is not a simplification of
the one-authority design. Implement one Frankengate lifecycle in Aurora.

### Graphiti as a product conflicts with the minimal architecture

Graphiti requires a graph backend and does not make its grouping key a Frankengate
authorization proof. Most launch questions need bounded neighborhood or temporal
fact queries that relational edge tables and recursive SQL can answer. A graph
database is justified only if a real, authorized multi-hop question set fails the
relational benchmark—not because temporal facts are useful.

### Automatic memory and self-improvement create circular evidence

If a memory influences a later answer, that trace cannot independently corroborate
the memory. If a skill selected by a router receives the whole task reward, the
system cannot know that the skill caused success. If model output becomes memory and
then future output repeats it, frequency is not truth. Record influence lineage,
retain holdouts, test memory-on/off, and keep promotion separate from extraction.

### Trace-only replay does not establish real-world effects

A recorded trajectory can test whether expected steps appeared. It cannot establish
that a changed model would act the same way or that a tool altered external state.
Prospective replay needs immutable fixtures or read-only shadows. Stateful tools
need independent state-delta evidence and often human/business outcome validation.

### Fine-tuning conflicts with deletion and mutable knowledge

Mutable corporate facts, current policies, identities, permissions, and project
state belong in authorized retrieval and temporal fact tables. Weight updates make
source attribution, correction, deletion, and rollback harder. Fine-tune only stable
behavior after reversible prompt, skill, tool, retrieval, and routing changes fail
on a never-train holdout.

### Cross-user learning can become surveillance even without names

Rare clusters, exact identifiers, affected-user counts, time filters, and repeated
aggregate queries can re-identify people. Cross-user output should first be a
minimized pattern or reusable artifact. Introductions are reciprocal opt-in.
Managers receive no raw drilldown, employee “friction score,” or inferred
productivity/skill ranking.

## Can the system answer the intended enterprise questions?

| Question | Feasible answer | Required evidence | What must be refused |
|---|---|---|---|
| Who is doing the same work? | “These authorized task attempts share objective/tool/artifact/environment dimensions; an anonymous reusable pattern exists; request a reciprocal introduction.” | Adjudicated task boundaries; multi-dimensional task signature; authorized exemplars; stable cluster; minimum cohort and anti-differencing tests | Named people from vector proximity; “same job” or productivity inference |
| What cloud or domain skills are missing? | “This task family may benefit from capability X; here are the observed blockers, alternatives, resource, and a private optional check.” | Organization skill ontology linked to tasks; NIST NICE-like task/knowledge/skill structure; role/environment/permission controls; verified outcomes; user or expert validation | “Employee X lacks AWS/Kubernetes skill” from chat style, failure count, or judge label |
| What work are humans actually doing? | “These gateway-mediated task families are represented with this coverage; these sources and off-platform activities are invisible.” | Capture manifest, adapter loss receipts, sampling propensity, source coverage, task labels | Total workload, effort, loyalty, performance, or work not observed by Frankengate |
| Where do people struggle three or four times before success? | “These attempt sequences contain repeated accidental friction and a candidate recovery delta.” | Attempt lineage, ordered deltas, independent first-success outcome, environment snapshots, productive-exploration label | Calling the final change causal without add/remove replay or experiment |
| Which people or teams should talk? | “A shared reusable pattern exists; both parties can opt into an introduction around an artifact.” | Independent examples, shared structured context, incident/template confounder removal, mutual consent | People finder, manager reveal, or exposing who struggled |
| Should we suggest a prompt, skill, tool, memory, model, or fine-tune? | “The lowest-cost reversible intervention matching the diagnosed cause is proposed; its expected benefit is being measured.” | Attribution hypothesis; intervention registry; exposure/control; verified outcome; safety/cost/latency; rollback | Selecting an intervention only because similar text previously preceded success |
| What should become `MEMORY.md` or harness memory? | “This cited, scoped, editable candidate is proposed for destination X and expires/revalidates at Y.” | Stable repeated fact or convention; source citations; contradiction handling; audience and destination; approval; deletion lineage | Direct transcript dump, automatic cross-user memory, policy written by the model, in-place silent update |
| What should become an eval? | “This recurring or high-impact trace failure is reconstructed as a versioned audit or replay case with these assertions.” | Canonical trajectory; target failure; deterministic/semantic assertions; evaluator version; mutants; scope-safe fixture | Assuming one strange trace is prevalent or a retrospective matcher proves future behavior |
| What should train an embedding or generator? | “These reviewed, purpose-authorized examples cover a measured failure that simpler methods could not fix.” | Frozen benchmark; consent/purpose; source lineage; user/tenant/time split; hard-negative review; privacy/memorization/deletion tests | Mining every successful trace as a positive pair or every failed trace as a negative |

The system can answer these questions, but mostly as **evidence-backed,
privacy-bounded hypotheses and experiments**, not as omniscient enterprise facts.

## Skill and capability inference

Use an organization-owned ontology whose primitives resemble the
[NIST NICE Framework](https://www.nist.gov/itl/applied-cybersecurity/nice/nice-framework-resource-center/getting-started):

- **task:** an observable activity toward an objective;
- **knowledge:** concepts required to perform a task;
- **skill:** capacity to perform an observable action;
- **resource/intervention:** course, document, runbook, skill package, tool, or
  supervised exercise that can improve performance;
- **evidence:** observed action/outcome and its provenance—not prose style.

AWS exam guides and other role frameworks can seed terminology, but they cannot
prove employee competence. Maintain organization-specific mappings such as:

```text
task family
  -> required observable capabilities
  -> acceptable evidence and counterevidence
  -> known environmental blockers
  -> learning resources
  -> optional practical eval
  -> expiry/review owner
```

Surface private “support opportunity” cards first. Enterprise learning views show
aggregate task/capability demand and missing shared artifacts, not individual gaps.

## Feedback loop and intervention ladder

Every recommendation must enter an intervention registry:

```text
diagnostic hypothesis
  -> candidate intervention
  -> user/team approval
  -> exposure assignment
  -> observed use
  -> independent outcome
  -> delayed outcome and harm checks
  -> promote, revise, retire, or abstain
```

Choose the lowest-cost, most reversible intervention consistent with the evidence:

1. fix permission, incident, environment, tool description, or missing telemetry;
2. repair a canonical knowledge source or exact retrieval alias;
3. improve retrieval/chunking/reranking;
4. suggest a prompt;
5. propose a procedural skill/playbook;
6. propose scoped memory;
7. change routing or model;
8. adapt the embedding model;
9. fine-tune a generator.

This order is not dogma. It is a causal and operational prior: do not encode a
missing permission into model weights.

## Embeddings and custom model decision

The launch benchmark must compare:

1. typed SQL and exact identifiers;
2. PostgreSQL FTS/trigram;
3. structured trajectory/task signatures;
4. a strong general embedding model;
5. exact + lexical + dense hybrid;
6. hybrid plus reranker;
7. only then a domain-adapted embedding.

Use task- or attempt-level vectors, not one vector per raw span. Keep separate
representations for task intent, failure signature, recovery delta, knowledge
need, and procedural pattern. A single “whole trace” vector blurs the distinctions
the product needs.

The [pgvector](https://github.com/pgvector/pgvector) exact scan is the recall
oracle. Its approximate indexes apply filters after candidate scanning, so highly
selective RLS/classification filters need per-scope recall tests, iterative scans,
overfetch, partitioning, or exact fallback.

Fine-tune an embedding only when a frozen, purpose-limited corpus shows a named
critical failure in the general hybrid baseline. Training should use reviewed
positive pairs and hard negatives, because automatic hard-negative mining can
create false negatives. The [NVIDIA domain-specific embedding guide](https://huggingface.co/blog/nvidia/domain-specific-embedding-finetune),
[FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding), and
[Sentence Transformers](https://github.com/huggingface/sentence-transformers)
provide implementation patterns, not proof that corporate trace labels are valid.

Embedding adaptation may improve candidate recall. It will not solve task
segmentation, skill attribution, causal intervention choice, authorization, or
memory truth.

## Aurora, JSONB, graph, and vector feasibility

Aurora remains the smallest viable architecture:

- normalized columns for identity, authority, classification, time, state,
  ownership, revisions, outcomes, and join keys;
- JSONB for provider/harness-specific long-tail attributes, loss manifests,
  detector receipts, evaluator explanations, and source-specific payload metadata;
- FTS/trigram for text and identifiers;
- pgvector for sparse task/attempt/fact/playbook embeddings;
- relational node/edge and bitemporal fact tables;
- materialized or incremental aggregate tables;
- durable asynchronous jobs;
- conditional S3 blobs referenced by authorized manifests.

Do not hide authority, time, state, outcome, or high-selectivity filters inside
JSONB. Do not put every span into an ANN index. Do not introduce a graph database
until real bounded questions defeat relational recursive queries.

Aurora’s supported pgvector extension and current storage capacity are sufficient
to test this design. [Aurora documents storage scaling up to 256 TiB](https://docs.aws.amazon.com/rds/latest/auroraextendedcontent/aurora-faq-scalability.html);
the several-hundred-GB corpus is not a capacity-driven database migration.

Move to one managed extensible PostgreSQL—or self-host the same one-database
design—only after a preregistered requirement fails:

- authorized filtered-vector recall/latency fails after vector cardinality
  reduction, exact fallback, partitioning, and normal pgvector tuning;
- a required lexical workload cannot meet quality/SLOs with PostgreSQL search;
- actual graph questions cannot be answered within budget by relational edges;
- extension benefits exceed the HA, PITR, upgrade, failover, WAL, monitoring, and
  staffing cost of leaving Aurora.

VectorChord, pgContext,
[TurboVec](./turbovec-frankengate-fit-review.md), or another index can change a
measured query performance boundary. None can make a skill inference valid or a
memory true.

## Required native data model

The minimum authoritative families are:

- trace sources, import receipts, adapter revisions, and loss manifests;
- sessions, canonical nodes, canonical edges, and content/object manifests;
- tool proposals, authorization decisions, executions, observations, and state
  deltas;
- task attempts, task signatures, attempt lineage, and verified outcomes;
- authority envelopes, audiences, classifications, consent/purpose grants,
  authorization/deletion epochs, and source-use lineage;
- deterministic features, signal releases, sampling propensities, and detector
  receipts;
- annotations, adjudications, appeals, corrections, and evidence-status claims;
- task/capability ontology, skill hypotheses, and learning resources;
- facts/entities/relations with valid-time, system-time, contradiction, and
  provenance;
- dataset/eval/experiment revisions and evaluator calibration;
- memory and playbook candidates, releases, destinations, influences, expiry,
  rollback, and deletion closure;
- intervention proposals, exposures, controls, outcomes, and harms;
- privacy-tested aggregate releases and reciprocal collaboration escrow;
- embedding/index/reranker releases and exact-recall benchmark receipts.

Every derived object carries source IDs, authority scope, classification, purpose,
revision, created/valid times, deletion lineage, and evidence status.

## Build sequence and stop/go gates

### Gate 0: Can the evidence be represented?

- Import representative native and external histories.
- Preserve branches, tools, retries, fallbacks, delegation, and loss receipts.
- Link tool proposals to authorization, execution, observation, and external
  outcome where available.
- Stop if material trajectory meaning is silently lost.

### Gate 1: Can users trust personal history?

- Full current-authority RLS lattice, not tenant-only RLS.
- Personal history, exact/lexical search, missingness/status explanations,
  correction, deletion, export, and appeal.
- Stop team/enterprise work if any cross-scope row, identifier, count, distance,
  snippet, cache entry, or object reference leaks.

### Gate 2: Can humans agree on the labels?

- Label task boundaries, task similarity, accidental/productive friction,
  recovery, verified outcomes, and `insufficient_evidence`.
- Use blinded annotation, adjudication, user/tenant/time holdouts, and random
  sampling beside signal-selected traces.
- Stop automated diagnosis if it cannot beat deterministic/exact baselines.

### Gate 3: Do retrieval and Aurora meet the real workload?

- Exact/FTS/structured/base-dense/hybrid/reranker ablations.
- Exact authorized vector oracle by RLS/classification selectivity.
- Concurrent ingest/search/delete/re-embed/aggregate/failover/cost gauntlet while
  inference SLOs remain protected.
- Change databases only on a declared failure, not anticipated optionality.

### Gate 4: Do suggestions cause benefit?

- Test prompts, skills, retrieval, memory, routing, and models with control,
  replay, shadow, canary, A/B, or stepped-wedge designs.
- Measure verified success, turns, latency, cost, corrections, anchoring,
  regressions, privacy, and delayed harm.
- Keep causal language disabled until the intervention gate passes.

### Gate 5: Is cross-user learning useful after privacy controls?

- Stable cohorts, contribution bounds, minimum cohort, complementary suppression,
  query-history accounting, rare-person canaries, contestability, and reciprocal
  opt-in.
- Release patterns and minimized artifacts, not identities.
- Kill enterprise pattern claims if privacy controls remove utility or attacks
  recover people/classified material.

### Gate 6: Is model adaptation still needed?

- Train an embedding adapter only after a frozen hybrid retrieval failure.
- Fine-tune a generator only after prompt/skill/tool/retrieval/routing
  interventions fail on stable behavior.
- Require immutable manifests, purpose-specific authorization, memorization and
  deletion tests, temporal/tenant/user holdouts, rollback, and no cross-customer
  training by default.

## Kill criteria

Do not build or narrow the relevant claim if:

- canonicalization cannot preserve important source semantics;
- independently verified outcomes are too sparse for attribution;
- human agreement on task/recovery/skill labels is too low;
- cross-user patterns are not useful after privacy controls;
- suggestions do not improve outcomes against a control;
- embeddings do not beat exact/lexical/structured baselines on a named slice;
- domain adaptation improves average retrieval but harms authorization, deletion,
  hard-negative, identifier, latency, or rollback slices;
- analytics materially harms inference isolation or exceeds its declared cost;
- the organization will not prohibit manager drilldown and individual
  productivity/skill scoring.

## Immediate decision

Build **a personal evidence and eval-proposal product**, backed by the richer
Aurora evidence model. In parallel, create the label and experiment corpora that
can falsify task similarity, friction/recovery, skill-support, memory utility, and
enterprise-pattern claims.

Do not initially build:

- a manager workforce analytics dashboard;
- automatic memory injection;
- automatic cross-user introductions;
- custom embeddings;
- generator fine-tuning;
- a graph service;
- a second search/vector/log database;
- Phoenix, Opik, or Langfuse as another authority.

Those are earned by evidence, not prerequisites.

## Primary sources

- [Microsoft AgentRx](https://github.com/microsoft/AgentRx)
- [Signals: inexpensive signals for selecting informative agent traces](https://arxiv.org/abs/2604.00356)
- [AgentEvals](https://github.com/agentevals-dev/agentevals)
- [Arize Phoenix](https://github.com/Arize-ai/phoenix)
- [OpenInference](https://github.com/Arize-ai/openinference)
- [Opik](https://github.com/comet-ml/opik)
- [Langfuse](https://github.com/langfuse/langfuse)
- [Microsoft OpenRCA](https://github.com/microsoft/OpenRCA)
- [Graphiti](https://github.com/getzep/graphiti)
- [LangMem](https://github.com/langchain-ai/langmem)
- [Amazon MemInsight](https://github.com/amazon-science/MemInsight)
- [Anthropic Dreams](https://platform.claude.com/docs/en/managed-agents/dreams)
- [Google ReasoningBank](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/)
- [Microsoft LEGOMem](https://www.microsoft.com/en-us/research/publication/legomem-modular-procedural-memory-for-multi-agent-llm-systems-for-workflow-automation/)
- [Microsoft ACE](https://www.microsoft.com/en-us/research/publication/agentic-context-engineering-evolving-contexts-for-self-improving-language-models/)
- [Anthropic Bloom](https://www.anthropic.com/research/bloom)
- [OpenAI self-improving tax agents](https://openai.com/index/building-self-improving-tax-agents-with-codex/)
- [NIST NICE Framework](https://www.nist.gov/itl/applied-cybersecurity/nice/nice-framework-resource-center/getting-started)
- [pgvector](https://github.com/pgvector/pgvector)
- [Aurora PostgreSQL supported extensions](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Extensions.html)
- [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [OpenTelemetry semantic conventions](https://github.com/open-telemetry/semantic-conventions)
