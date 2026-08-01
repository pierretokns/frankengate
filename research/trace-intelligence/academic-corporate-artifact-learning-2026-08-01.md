# Corporate trace learning: literature map and research seam

Date: 2026-08-01  
Status: research synthesis; no production adoption

## Executive conclusion

The literature is not empty. It is fragmented across validated agent skills,
enterprise hard-negative retrieval, schema linking, SQL workload mining, event-log
representation, and cheap-model/frontier cascades. The closest published systems are
NVIDIA ASPIRE, NVIDIA ENPIRE, SAP TRACE, the enterprise hard-negative mining work of
Meghwani et al., and corpus-adaptive schema retrieval. None of the reviewed systems
combines all of the following in one evaluated loop:

1. raw Claude/Codex/OTel traces with tool calls and branches;
2. a corporate alias/entity layer that preserves same-name collisions;
3. executable SQL/tool artifacts, including failed attempts and repairs;
4. schema, dialect, authorization, freshness, and tenant constraints;
5. cross-user/team transfer with independent replay and rollback gates; and
6. a measured embedding → small-model → frontier adjudication cascade.

That intersection is a credible systems-and-empirical research seam. The claim should
not be “memory helps agents”; it should be “validation-carrying corporate artifacts
can be mined from traces and safely reused under schema, identity, and authority
drift.”

## Closest precedents

### Validated skills and replay

- [NVIDIA ASPIRE](https://research.nvidia.com/labs/gear/aspire/) records fine-grained
  execution observations, diagnoses failures, repairs code-as-policy, re-executes the
  repair, and stores validated fixes as reusable skills. It evaluates on disjoint
  debug/evaluation seeds and explicitly lists stale, redundant, overly-specific
  memory and compute cost as unresolved limitations. It is a robotics system, not an
  enterprise data system, but its admission rule is directly portable.
- [NVIDIA ENPIRE](https://research.nvidia.com/labs/gear/enpire/) makes the feedback loop
  explicit: reset, execute, verify, improve, and repeat. Its environment, rollout,
  policy-improvement, and evolution modules are the right abstraction for a replayable
  corporate tool/query environment. A Frankengate analogue needs resettable fixtures,
  independent outcome oracles, and versioned artifacts.
- FlowEvo, Tool Forge, AgentSM, SkillDisCo, and related work provide useful registry,
  procedural-subgraph, and structured-execution-memory designs. Their reported gains
  remain benchmark-specific; FlowEvo has no repository test suite in the checkout we
  inspected, and Tool Forge’s local run needs Python/dependency alignment.

### Enterprise retrieval and hard negatives

- [Hard Negative Mining for Domain-Specific Retrieval in Enterprise Systems](https://aclanthology.org/2025.acl-industry.72/)
  dynamically chooses semantically close but contextually irrelevant documents and
  reports +15% MRR@3 and +19% MRR@10 on a cloud-services corpus. This directly supports
  mining same-nickname/wrong-system pairs rather than random negatives.
- [Finding the Right Tables and Columns](https://arxiv.org/abs/2607.13311) treats
  schema linking as a standalone retrieval task. Corpus-adaptive query synthesis plus
  granularity-aware hard negatives improves average Recall@10 from 60.4 to 75.6 and
  transfers in leave-one-corpus-out tests. This is the nearest evidence for a custom
  corporate schema retriever.
- [TRACE](https://arxiv.org/abs/2607.22639) shows that realistic enterprise tool
  retrieval is dominated by overlapping tools and business rules; an embedding-only
  baseline can be weak, while rule-grounded training improves retrieval. Frankengate
  should test real terse user requests and ambiguity tiers, not only verbose catalog
  descriptions.
- DCG-SQL, LitE-SQL, Memo-SQL, Query Capsules, Query & Conquer, LinkedIn’s enterprise
  SQL assistant, and Alibaba Workload Miner show complementary pieces: structural
  retrieval, schema-aware negatives, failure-to-fix memory, typed SQL skeletons,
  execution-level equivalence, team/workload context, and online workload clustering.

### Raw logs, process structure, and cascades

LogKG, LEKG, SLOGERT, process mining, LogHub/Drain3/LUNAR, AdaptiveLog, and LogAn
demonstrate that raw text alone is a poor representation of cases, activities,
relations, and outcomes. First construct sessions, event graphs, tool/API entities,
tests, and artifact links; then apply lexical/dense retrieval. AdaptiveLog is a useful
cascade template: use a small model and uncertainty to route only difficult cases to a
frontier model. The reported savings are not a guarantee for corporate semantics and
must be measured with an independent reference sample.

## What is close, adaptable, or far

| Family | Distance | What transfers | What does not transfer automatically |
|---|---|---|---|
| ASPIRE/ENPIRE | Near-exact mechanism | replay, outcome gate, validated skill admission, disjoint evaluation | robotics reset/sensors; fixed primitive APIs |
| Enterprise hard negatives, schema retrieval, SAP TRACE | Near-exact retrieval problem | collision-aware negatives, corpus adaptation, business rules, ambiguity tiers | catalog data is cleaner than raw agent histories |
| Memo-SQL/Query Capsules/Query & Conquer | Close SQL artifact design | preserve failures, typed placeholders, execution/result equivalence | public datasets do not model multi-tenant authority or drift |
| Workload mining/query recommendations | Close operational analogue | cross-user query fragments, workload groups, execution features | recommendations are not necessarily reusable governed tools |
| Log KG/process mining | Adaptable representation | event/session graphs, relations, temporal provenance | event-log case IDs and outcomes must be reconstructed |
| Splink/Senzing/DerwenAI entity resolution | Adaptable identity layer | canonical IDs, aliases, source/temporal provenance, abstention | entity truth cannot be inferred from embedding similarity alone |
| Generic vector RAG/episodic memory | Far for the core claim | candidate generation and evidence previews | no execution, identity, freshness, authority, or rollback semantics |
| Robotics skill libraries/Voyager | Far domain, useful pattern | procedural packaging and library APIs | no enterprise schemas, permissions, dialects, or real user intent |

## Frankengate artifact contract

An artifact should be a versioned executable capsule, not a text chunk:

- normalized user intent and task family;
- parameterized SQL/tool procedure or repair;
- typed placeholders and dialect;
- schema/catalog fingerprint, lineage, and join grain;
- system/team/tenant and authorization scope/epoch;
- source trace/span hashes and branch ancestry;
- observed success or failure, error taxonomy, and correction;
- result-shape/value fingerprint and plan/cost/latency evidence;
- freshness, expiry, revocation, and migration rules;
- independent replay count, evaluator, confidence, and release state;
- negative-memory links for known failure modes and unsafe near misses.

Retrieval must be three-pool and filtered: exact/BM25 identifiers, dense semantic
neighbors, and graph/metadata neighbors. A reranker or frontier model may adjudicate
the gray zone, but canonical IDs, schema/authority filters, and execution validation
remain deterministic gates.

## Hard-negative recipe

1. Canonicalize mentions into services, repositories, databases, schemas, tables,
   columns, tools, workflows, errors, and artifacts with time/version and scope.
2. Mark weak positives only when reuse, independent execution, or reviewed acceptance
   supports them; repeated co-occurrence is a candidate, not truth.
3. Mine lexical, dense, graph-neighbor, and same-identifier candidates.
4. Label collision families: same alias/different system, same schema words/wrong
   join or grain, same question/different authority, stale version, semantic-result
   mismatch despite successful execution, and near-duplicate failure traces.
5. Use frontier adjudication or human review only on high-value/ambiguous candidates;
   retain gray-zone and NIL/abstain labels.
6. Re-mine after every embedding/index version; stale negatives invalidate conclusions.

Measure Recall@K/MRR, same-name false-merge rate, NIL/abstention, stale/unauthorized
retrieval, artifact execution success, result equivalence, and latency/cost on
time-, team-, schema-, and unseen-system splits.

## Embedding versus model mining

The first empirical cascade should compare:

1. deterministic template/session signals and SQL/FTS;
2. lexical + dense candidate retrieval;
3. small-model extraction/classification over every candidate;
4. dense → small model;
5. signals → dense → small → frontier adjudication;
6. a frontier-only reference sample.

Keep selection, extraction, adjudication, and downstream artifact utility as separate
scores. Malformed JSON is a failure, not a null. Cheap models are promising for
template labels, cluster summaries, and candidate normalization; frontier models or
humans remain necessary for ambiguous enterprise meaning and SQL correctness until
measured otherwise.

## Historical Claude/Codex trace research stream

The new companion program is tracked in GitHub #125–#129. It asks how to mine months
or 100GB-scale histories for productive iteration versus genuine friction, infer user
intent, and generate replayable evals. The critical distinction is evidence level:

- observed: explicit user correction, test/build result, tool error, accepted patch;
- weak: rephrase, retry, branch abandonment, escalation, repeated search;
- inferred: model- or heuristic-derived intent/friction;
- unknown: no independent outcome or user confirmation.

Do not equate repetition with failure or a final answer with satisfaction. Benchmark
creation should compare history-only intent inference with targeted clarification and
measure information gain, replay correctness, and downstream eval yield.

There is now direct precedent, so this is not an empty field:

- [Anthropic’s Claude Code expertise study](https://www.anthropic.com/research/claude-code-expertise)
  classifies transcripts and cross-checks model labels against telemetry, project
  context, files, vocabulary, corrections, verification, errors, failed tests, and
  repeated attempts. This supports transcript-plus-artifact intent inference, but its
  labels are probabilistic and task-specific.
- [Cursor’s semantic search work](https://cursor.com/blog/semsearch) retrospectively
  asks what search result would have helped earlier, uses those judgments to train an
  embedding, and combines semantic retrieval with grep. This is the closest public
  recipe for mining agent sessions into a task-specific retrieval model.
- [CursorBench](https://cursor.com/blog/cursorbench) uses real engineering sessions,
  short/ambiguous requests, agentic graders, and separate correctness, code quality,
  efficiency, and interaction measures. It is a useful evaluation design, not proof
  that all historical intents are recoverable.
- [SWE-bench](https://arxiv.org/abs/2310.06770) derives task intent from issue text,
  accepted patches, repository snapshots, and executable tests; [SWE-Gym](https://arxiv.org/abs/2412.21139)
  turns similar real tasks into resettable environments and trajectories. These make
  the expected artifact and verifier explicit, which is what raw Claude/Codex logs
  lack.
- [OpenAI’s SWE-Bench Pro audit](https://openai.com/index/separating-signal-from-noise-coding-evaluations/)
  found a material broken/underspecified task rate even in a curated benchmark. Every
  mined eval therefore needs independent review and a broken-task label.
- [OpenAI’s eval guidance](https://github.com/openai/evals/blob/main/docs/build-eval.md)
  recommends thematic consistency, challenge, directional clarity, spot checks, and
  human-calibrated model judges. Use these as release gates, not as a substitute for
  replay.
- [TraceLab](https://tracelab.cs.washington.edu/) provides a public proxy corpus with
  hundreds of thousands of Claude/Codex steps and tool calls. It is valuable for
  parser/segmenter preflight, but it does not provide private enterprise intent or
  satisfaction ground truth.

The practical extraction pipeline is: normalize a session/turn/action DAG; segment
episodes with uncertain boundaries; infer a candidate goal from the first prompt plus
loaded artifacts; detect friction from explicit corrections, reprompt similarity,
error→repair loops, test/build outcomes, denials, timeouts, stagnation, reverts,
branch abandonment, and escalation; emit a candidate work packet; run deterministic
checks; use independent frontier judges only for unresolved fields; then replay and
promote. A work packet should contain the task/persona/source bundle/tool catalog,
policy boundary, expected artifact, trace expectations, deterministic checks,
rubric, reviewer, evidence spans, counterfactual negative, and replay result.

Historical logs can produce useful candidate intent/evals without interviewing users.
They cannot reveal hidden business constraints or satisfaction reliably. A small,
stratified clarification/adjudication sample is needed to estimate false-friction,
missing-intent, and broken-eval rates. Preserve an explicit unknown/abstain state.

[Corpus2Skill](https://arxiv.org/abs/2604.14572), found again through CASS, is a useful
nearby design: it compiles a corpus into hierarchical summaries, embeddings, entity
indexes, cross-links, and navigable skills. Its gains were strongest on coherent
single-domain QA/RAG subsets and weaker on open-domain or tabular data, with no
incremental update path. Use it for candidate taxonomy/navigation experiments, not as
the evidence or outcome layer.

Classical process mining supplies the missing deterministic front end: event-log
segmentation, trace variants, conformance, multi-perspective clustering, and
representative-stratified sampling. It can combine activities, resources, timing,
errors, and outcomes before semantic modeling. It cannot recover hidden business
intent or satisfaction on its own, so the result must remain a candidate signal until
frontier/human calibration and replay.

## Empirical publication program

The first paper should be a narrow, preregistered systems study:

- **Artifact IR/registry:** validation-carrying SQL/tool capsules and lifecycle gates.
- **Representation:** raw trace → event graph/entity layer → exact+dense+metadata
  retrieval with collision-aware hard negatives.
- **Outcome:** independent replay/result equivalence, authority/freshness checks,
  rollback, and cross-team transfer.
- **Benchmark:** terse real requests, failure→fix pairs, schema/version drift, and
  unseen-system splits; public traces plus sanitized local traces.

Likely venues: SIGMOD/VLDB/PVLDB for workload/artifact systems; ACL Industry or
EMNLP Industry for schema/alias retrieval; ICSE/FSE for trace/replay/eval lifecycle;
ICPM/BPM for process mining. NeurIPS/ICML is appropriate only if a representation or
cascade generalizes beyond one enterprise.

### Partner shortlist

- **MIT DSAIL / Sam Madden:** their official mission explicitly targets learned
  components for indexes, query optimization, schema design, enterprise data
  integration, and systematic data/model lifecycle management; they report deep
  industry collaboration. This is the strongest first contact.
- **Harvard DASlab / Stratos Idreos:** self-designing data/AI systems, adaptive
  indexing, workload-tailored storage, and interactive exploration fit the artifact
  retrieval layer.
- **MIT Jacob Andreas / Language and Intelligence:** language-grounded program and
  procedure learning fits intent and skill representations, as a complementary
  coauthor rather than the systems lead.
- **NVIDIA GEAR/UMich SymbioticLab/UC Berkeley AUTOLab:** ASPIRE/ENPIRE authors are
  unusually close methodologically; a collaboration would require a clear corporate
  data-system contribution rather than a robotics port.

Start with a two-page problem statement, sanitized benchmark and preregistered
factorial—not a broad product pitch. Route sponsored research, NDA, and data-use
agreements through the relevant university research offices.

## Current evidence boundary

Our earlier local results do not yet prove universal skill improvement or enterprise
transfer. Some natural-memory and skill interventions were null or underpowered; the
finance embedding benchmark used an off-the-shelf Balyasny multilingual-e5-base, not a
Frankengate-trained model. The next valid claim requires a powered, family/time/team
disjoint artifact-reuse and friction-to-eval study with independent outcome checks.

## Historical CASS provenance

CASS searches on 2026-08-01 found the State of AI skill-discovery work and the prior
three-layer pipeline (local trace mining → centralized curation → frontier
distillation), plus the existing finance embedding and benchmark threads. CASS index
was refreshed before search; semantic search was unavailable, so these are lexical
matches and should be treated as discovery pointers, not primary evidence.
