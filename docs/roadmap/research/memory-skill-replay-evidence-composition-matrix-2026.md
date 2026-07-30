# Memory, skill learning, and replay: evidence and composition matrix

**Status:** source-pinned architecture audit plus deterministic conformance
**Reviewed:** 2026-07-30
**Decision scope:** which memory, dreaming, skill-learning, temporal-graph, and
RL/replay mechanisms can be combined in Frankengate's governed PostgreSQL
architecture

## Decision

The concepts can be combined, but the reviewed projects cannot be stacked as
production services.

Frankengate should keep one governed relational evidence plane and add typed
records for memory candidates, immutable releases, dependency edges,
evaluations, replay manifests, and influence lineage. Anthropic Dreams,
Graphiti, LangMem, MemPalace, ReasoningBank, Hermes, and RL environments should
remain source mechanisms or experimental arms. Their native stores and mutable
files must not become parallel systems of record.

The composition is technically useful only when the following types remain
distinct:

```text
observed event
  -> model-inferred candidate
  -> reviewed immutable release
  -> harness projection
  -> influenced trajectory
  -> independent held-out evaluation
```

A summary is not evidence, an outcome is not a reward explanation, a successful
trace is not proof that every step was correct, and a harness file is not an
authorization boundary.

## Evidence-state definitions

| State | Meaning |
|---|---|
| Literature/source only | A mechanism is documented in a primary paper, product contract, or pinned repository. Frankengate has not represented or executed it. |
| Schema-supported | Current or proposed Frankengate records can represent the mechanism without flattening away its semantics. |
| Implemented | Frankengate code executes the mechanism. A prose design or third-party implementation does not count. |
| Empirically tested | A reproducible Frankengate experiment exercised the mechanism and emitted aggregate results. Synthetic conformance and natural-trace quality are reported separately. |

## Evidence matrix

| Concept | Primary mechanism and pin | Frankengate schema support | Implementation | Empirical status | Boundary |
|---|---|---|---|---|---|
| Anthropic Dreams | Asynchronous copy-on-write consolidation from selected sessions into a separate store; beta `dreaming-2026-04-21` ([docs](https://platform.claude.com/docs/en/managed-agents/dreams)) | **Proposed**, not in the current SQL: job, input release, status, candidate set, output release, and rollback are missing | No model-equivalent OSS implementation | **Synthetic mechanics only:** failed-job isolation and copy-on-write release passed | Managed black box; no arbitrary ATIF/OTel input, public evidence schema, RLS contract, or reproducible extractor |
| OpenAI dreaming | Background memory refresh for usefulness, preference adherence, and currentness ([product description](https://openai.com/index/chatgpt-memory-dreaming/)) | Eval dimensions can be represented as typed evaluations; current SQL has only generic JSONB outcomes/artifacts | Not implemented | Not tested | Product behavior, not a public algorithm or artifact contract |
| MemPalace | Verbatim retrieval, deterministic IDs, temporal metadata; `v3.6.0` / `8ab251c` ([source](https://github.com/MemPalace/mempalace/tree/8ab251c452c43f2b07a76a28f2433e258307f571)) | Verbatim evidence fits trajectory/event tables; contextual valid/system time and release membership do not | No native integration | **Synthetic temporal/provenance mechanics only** | Its pgvector namespace/table convention is not RLS; it is a retrieval baseline, not a learning engine |
| `jeffpierce/memory-palace` | Typed extracted memories and relation edges; `v2.0.1` / `fd88282` ([source](https://github.com/jeffpierce/memory-palace/tree/fd88282c1e2404d35d284dd09f622b4c1ec9b506)) | Types and edges fit proposed candidate/dependency tables | Not implemented | Not tested | Direct writes, optional scoping, and weak evidence spans conflict with proposal-only release |
| Graphiti | Episode provenance, entity/fact edges, valid-time invalidation, hybrid retrieval; `v0.29.3` / `021d3a5` ([source](https://github.com/getzep/graphiti/tree/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d)) | **Proposed relational subset:** fact/context identity, valid time, evidence edges, contradiction and invalidation | No Graphiti service or extractor integration | **Synthetic subset:** contextual contradiction, valid/system time, and deletion closure passed | `group_id` is not authorization; stochastic multi-service extraction and a graph database add an unnecessary authority and operations surface |
| LangMem | Schema-guided create/update/delete memory operations; commit `56d8593`, package `0.0.30` ([source](https://github.com/langchain-ai/langmem/tree/56d85939d80bb731bd5e237567148d817d7bfd16)) | Candidate payloads fit proposed typed candidates; current artifacts lack evidence, validity, and authority intersection | Not implemented | **Synthetic candidate lifecycle only** | Store namespaces are not RLS; direct mutation must be converted into proposals |
| ReasoningBank | Induce lessons from successful and failed experiences, retrieve them for later tasks; `ed80611`, package `0.1.0` ([source](https://github.com/google-research/reasoning-bank/tree/ed80611788292ea739f1effd31f16c53823b8a0d), [research summary](https://research.google/blog/reasoningbank-enabling-agents-to-learn-from-experience/)) | Lessons fit candidates; success/failure evidence needs typed evaluations and exact event links | No ReasoningBank runner | Not tested | Direct append, self-judging, and benchmark-specific retrieval contaminate independent validation |
| Hermes stable memory | Files, provenance, protected writes, snapshots, curator, and rollback; `v2026.7.20` / `3ef6bbd` ([source](https://github.com/NousResearch/hermes-agent/tree/3ef6bbd201263d354fd83ec55b3c306ded2eb72a)) | Harness projections and version lineage are proposed; files cannot carry database authority | No integration | Source tests were reviewed; no Frankengate outcome test | A reflection can still directly mutate shared files without held-out outcome evidence |
| Hermes Self-Evolution | GEPA/MIPRO scaffold over examples and a skill; `0a929e3` ([source](https://github.com/NousResearch/hermes-agent-self-evolution/tree/0a929e3aa20e15cf04dc7c28492a7d41a5139125)) | Candidate variants/eval runs fit proposed schema | Not adopted | Targeted source review found the optimizer does not mutate the claimed skill body and a caller violates its own structure contract | Not a valid empirical baseline in the reviewed revision |
| GEPA / Trace2Skill / SkillOpt family | Propose and select bounded text artifacts using rollout feedback and executable validation | Candidate provenance, split manifests, evaluation runs, signed releases, exposure, influence, and withdrawal are represented in `005` | Governed tool boundary, Trace2Skill launcher, PostgreSQL lifecycle, and a three-arm NL2SQL mechanics runner are implemented for research | **Mechanics only:** the 12-episode Defog P0 gave every arm the same 2/4 passes and failed its terminal-protocol gate; no trace-mined artifact or skill-benefit estimate has run. The 18/18 PostgreSQL lifecycle assertions still pass | Search strategy is composable; native mutable skill writers, self-selected tests, and effect screening before the failed protocol gate are not |
| “Jeopard” | Exact requested project remains unresolved after repository/paper search | None attributable | None | None | Do not silently equate an unknown project with GEPA or another similarly pronounced name |
| RL environment episode | Reset, action, observation, termination, task/resource state; OpenEnv `v0.4.1` / `65c506e` ([source](https://github.com/meta-pytorch/OpenEnv/tree/65c506ef94bb1f7279cb4359673b3ef81031d01f)) | Current event graph represents actions/observations but lacks required environment attachment | Adapters exist for some public fixtures, not a production environment contract | Adapter/projection fixtures only | A flat chat or ATIF sequence does not preserve reset state, resources, overlap, or replay divergence |
| Reward/evaluation evidence | Versioned checks and breakdowns; τ²-bench `v1.0.1` / `fc0055d` ([source](https://github.com/sierra-research/tau2-bench/tree/fc0055dc4e0a316c3f83133267fbd6faaa770992)) | `evaluation_runs` records independent versioned outcomes, security vetoes, cost, and latency; assertion-level evidence remains future work | Append-only evaluator-only result writes implemented in research SQL | Role separation and release veto pass; reward validity has not been tested | Scalar reward cannot support diagnosis, relabeling, or independent verification |
| Replay | Immutable task/environment/artifact manifest plus attempt and divergence records; SWE-agent `v1.1.0` / `0f3acaf` ([source](https://github.com/SWE-agent/SWE-agent/tree/0f3acafacabc0def8cc76b4e48acb4b6cf302cb9)) | Frozen split/task/environment/tool/evaluator hashes are represented; full artifact and divergence attachments remain missing | End-to-end Defog mechanics runner records native tool calls and immutable attempt IDs; submitted candidates are not re-executed. Solver/evaluator process isolation remains open | 12/12 P0 episodes completed with valid authority and zero unauthorized observations, but protocol failures exceeded the preregistered gate and hidden remained sealed | Re-executing actions is not exact replay; the current same-process evaluator is acceptable only for mechanics and blocks P1 until capability-separated |
| Learner attachment | Token IDs, role/loss masks, behavior log probabilities, checkpoint/policy lineage; Agent Lightning `v0.3.0` / `3b5d733` ([source](https://github.com/microsoft/agent-lightning/tree/3b5d733861cf313fc09821a23240bbdf3cb2ee5b)) | Explicitly optional and currently absent | Not implemented | Not tested | Tokenizer- and policy-specific tensors are derivatives, not canonical evidence; store large payloads by content-addressed reference |
| Influence lineage | Record the release/candidate IDs that influenced a later trace | `release_exposures` and `trajectory_influences` preserve scoped release-to-trace lineage | Implemented in research PostgreSQL plus the deterministic oracle | **PostgreSQL RLS gate passed** for authorized influence and denied cross-subject influence | Candidate-level influence and prospective leakage analysis remain |

## Remaining representation gaps

The base
[`001_trace_research.sql`](../../../research/trace-intelligence/sql/001_trace_research.sql)
and lifecycle
[`005_skill_release_lifecycle.sql`](../../../research/trace-intelligence/sql/005_skill_release_lifecycle.sql)
now cover governed trajectories/events, many-source candidates, frozen
manifests, independent evaluation runs, signed releases, exposure, influence,
audit events, and withdrawal. They still do not cover the full architecture:

1. Candidate provenance currently covers many events, but not typed
   candidate-to-candidate, evaluation-to-claim, or transitive deletion edges.
2. Scope is typed and epoch-checked, but classification derivation and complete
   policy decision receipts are not first-class.
3. There are no `valid_from`/`valid_to` and `system_from`/`system_to` facts.
4. Releases are signed, parentable, withdrawable records, but diffs, atomic
   rollout pointers, canary decisions, and signature verification are absent.
5. There is no dream job, partial-output quarantine, deletion dependency graph,
   or export invalidation; release-to-trajectory influence exists, but not
   candidate- or assertion-level influence.
6. The canonical event schema has no normative top-level `environment`,
   `evaluation`, `replay`, or optional `learner` attachment.
7. Evaluations are append-only and versioned but lack assertion-level evidence
   and verifier artifact references.
8. There is no content-addressed artifact manifest for screenshots, DOMs,
   repository layers, Playwright traces, audio, or tensor payloads.

ATIF and OTel do not fill these gaps. ATIF is a useful portable conversation and
action projection. OTel/OpenInference is a useful causal and latency projection.
Neither defines environment state, replay, temporal memory truth, a governed
release, or an independent evaluation.

## Composition conflicts

| Combination | Works if | Fails when |
|---|---|---|
| Dreams + Graphiti temporal facts | The dream emits evidence-linked candidates and the release engine preserves contextual valid time | “Latest wins” replaces facts that are simultaneously true for different projects, environments, users, or jurisdictions |
| LangMem + governed memory | LangMem create/update/delete operations become untrusted proposals | Its store mutates live memory or treats a namespace as an authorization boundary |
| MemPalace + semantic retrieval | Verbatim text and exact identifiers remain primary evidence; embeddings are rebuildable derivatives | An embedding hit is promoted into a fact, or its per-namespace table convention substitutes for RLS |
| ReasoningBank + skill evolution | Success/failure contrast proposes lessons and a separate runner tests them on hidden families | The generator judges itself, retrieves its own candidate during evaluation, or trains and tests on related traces |
| Hermes + Frankengate | Frankengate publishes an approved, signed, reversible projection | `MEMORY.md`/`SKILL.md` is edited directly or treated as the source of truth |
| RL environments + canonical traces | Typed environment/evaluation/replay attachments retain state, reward basis, and missingness | Rollout objects, ATIF, or OTel spans replace canonical governed evidence |
| Graph traversal + PostgreSQL | Dependency and temporal edges are relational rows queried recursively; JSONB stores versioned payloads, not authority | A graph server becomes a second security model and deletion/invalidation must coordinate across stores |
| Team/enterprise learning + RLS | Derivatives receive the intersection of source authority and aggregates have support/privacy thresholds | Raw cross-user content is placed in a shared vector namespace or a team label is mistaken for consent |

## Enterprise-question coverage

| Enterprise question | Required evidence and method | Current evidence |
|---|---|---|
| Where does one user repeatedly struggle before succeeding? | Sessionized trajectories, deterministic stagnation/rephrase/loop/failure signals, task identity, ordered outcomes | Partially supported by signal/trajectory arms; not yet a longitudinal natural-user result |
| Which users are doing materially similar work? | Governed task representations, tool/artifact structure, exact identifiers, semantic features, time window, uncertainty, and minimum support | Not tested; trace similarity alone does not establish the same goal or permission to connect people |
| Which skill or cloud capability is missing? | A versioned capability ontology, evidence-linked gap hypotheses, counterfactual skill recommendation, and verified post-recommendation outcome | Not implemented or tested |
| Which prompt, skill, model, or tool should be suggested? | Candidate generation plus randomized/canary or matched held-out evaluation with cost, latency, safety, and per-family floors | Eval proposals are plausible; recommendation benefit is untested |
| What should enter a user's memory? | Repeated evidence, contextual validity, contradiction handling, candidate review, release, influence tracking, and deletion closure | Lifecycle mechanics pass synthetically; extraction quality and natural-user benefit are untested |
| What can be shared with a team or enterprise? | Evidence-scope intersection, consent/purpose, classification, minimum support, privacy-preserving aggregate, review, and appeal | Scope mechanics pass synthetically; group inference and privacy thresholds are untested |
| Should users working on similar tasks talk to each other? | Reciprocal opt-in, current task intent, organizational policy, calibrated similarity, explanation, and suppression of sensitive inference | Not supported; this is a product and policy decision, not a nearest-neighbor query |
| What should be fine-tuned? | Stable taxonomy, independently verified labels, influence/leakage receipts, train/test family split, drift monitoring, and deletion handling | Not supported yet; embeddings or model training would currently learn unverified and contaminated derivatives |

The architecture can collect the evidence needed to ask these questions. It
does not make the open-ended answers reliable by itself. The hard work is
versioned task/capability definitions, causal or held-out outcome measurement,
authorization, and calibrated abstention—not vector search.

## Smallest production data model

Add relational tables to the existing governed PostgreSQL deployment before
adding another database:

| Table | Minimum purpose |
|---|---|
| `memory_evidence` | Exact event/field references plus observed time and authority snapshot |
| `memory_candidate` | Typed inferred fact, preference, procedure, friction, eval, or relation; proposal/review state |
| `artifact_dependency` | Many-to-many evidence, candidate, evaluation, release, export, and deletion edges |
| `dream_job` | Input release/manifest, model/prompt/config pins, status, partial-output quarantine |
| `memory_release` | Immutable parented release, decision receipt, rollback/deletion-withdrawal kind |
| `memory_release_entry` | Candidate membership with contextual valid time |
| `memory_influence` | Which releases/candidates affected a request, response, recommendation, or replay |
| `evaluation` and `evaluation_assertion` | Append-only outcome, verifier revision, reward basis, assertion evidence |
| `replay_manifest` and `replay_attempt` | Frozen environment/task/tool/artifact inputs and observed divergence |
| `artifact_ref` | Content-addressed object metadata, classification, encryption, scanning, retention, and deletion state |

Every table carrying user- or team-derived data needs native RLS over tenant,
subject/team audience, purpose, classification, and current authorization epoch.
JSONB remains useful for versioned, sparse provider payloads, rubrics, and loss
receipts, but the fields used for authority, joins, temporal queries,
invalidation, and lifecycle must be typed columns.

Graphiti may still be run as an ephemeral extraction/retrieval ablation.
LangMem and ReasoningBank may still generate candidate payloads. GEPA may still
search a candidate frontier. None requires a production graph/vector database
unless measurements show a bottleneck that PostgreSQL cannot meet.

## New empirical evidence

The deterministic
[`bitemporal_memory_conformance.py`](../../../research/trace-intelligence/bitemporal_memory_conformance.py)
arm exercised the proposed relational lifecycle. Its aggregate result is
[`bitemporal-memory-conformance-2026-07-30.json`](../../../research/trace-intelligence/experiments/results/bitemporal-memory-conformance-2026-07-30.json).

It passed 15/15 assertions for:

- copy-on-write system history and contextual valid-time correction;
- failed-job isolation;
- authority intersection and fail-closed composition;
- rollback without mutation;
- transitive deletion to candidate, release, and export;
- influence exclusion from independent validation; and
- stale-epoch denial.

This is **implemented and empirically tested synthetic conformance**, not a
database, model-quality, natural-trace, or enterprise-benefit result. The next
PostgreSQL implementation in
[`005_skill_release_lifecycle.sql`](../../../research/trace-intelligence/sql/005_skill_release_lifecycle.sql)
and rollback-only
[`006_skill_release_assertions.sql`](../../../research/trace-intelligence/sql/006_skill_release_assertions.sql)
then passed 18/18 checks through separate proposer, evaluator, releaser, and
runtime roles. It covers complete-source authorization, hidden tests,
security-vetoed release, no scope broadening, immutable signed fields, exposure,
influence, withdrawal, and stale epochs. This is database lifecycle evidence,
not task benefit or Aurora operations evidence. The next mandatory gates are:

1. test concurrent promotion, epoch changes, deletion, rollback, and export
   invalidation under transactions;
2. run at least two independent extractors on admitted natural traces and score
   exact-evidence entailment, contradiction, temporal/context identity, and
   abstention;
3. replay proposed procedural skills on frozen schema-family-held-out NL2SQL
   environments; use SpreadsheetBench only as a cross-domain control; and
4. measure whether released memory or skill changes independently verified
   outcomes without cross-scope leakage or per-family regression.

## Issue acceptance state

- [Issue #99](https://github.com/pierretokns/frankengate/issues/99) has a
  governed OSS dreaming design and source review, but its natural-trace,
  Postgres RLS, concurrency, and held-out outcome gates remain open.
- [Issue #100](https://github.com/pierretokns/frankengate/issues/100) has the
  environment/evaluation/replay vocabulary and source-pinned design, but the
  canonical schema, relational tables, replay runner, and empirical matrix
  remain open.

Neither issue should be closed from literature review or this synthetic arm
alone.
