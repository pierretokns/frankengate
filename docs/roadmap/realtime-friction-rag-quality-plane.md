# Real-Time Friction, RAG Quality, and Knowledge-Gap Plane

## Purpose

Bifrost should turn production interactions into governed evidence about where an AI
system failed, without treating user sentiment, an LLM judge, or a retrieval score as
ground truth. This plane connects traces, evaluations, alerts, annotation, knowledge-gap
remediation, replay, and controlled promotion of versioned knowledge-base snapshots.

The launch invariant is strict: user text and model-generated proposals never mutate a
production knowledge base directly. They create evidence-backed proposals that pass
provenance, privacy, ownership, replay, canary, and approval gates.

All content capture and reuse also passes the separate privacy boundary specified in
`docs/roadmap/privacy-redaction-and-learning-boundaries.md`. Friction analytics defaults
to derived events and sanitized evidence rather than raw conversations.

Required build order is explicit: `PrivacyTransformReceipt` contract -> sanitized trace
sink -> canonical RAG records and evaluators -> voluntary friction capture -> calibrated
friction inference -> governed remediation proposal -> immutable KB shadow/replay ->
tenant-sticky canary and audited promotion. No later stage may create an alternate raw-
content path around an earlier privacy or entitlement boundary.

## Architectural boundary

The Go gateway owns normalized events, policy, sampling, immutable revisions, job
control, lineage, alerts, and promotion decisions. Expensive or executable work runs in
sandboxed asynchronous workers: judge models, RAGAS, DeepEval, RAGChecker, ARES,
Giskard, NeMo Evaluator, garak, Python graders, embedding jobs, and training systems.

OpenTelemetry/OpenInference trace identifiers are the join key. Large prompts,
responses, chunks, and evaluator artifacts live in encrypted object storage; control
records contain hashes and authorized references rather than payload copies.

## Canonical records

Every record is versioned and tenant/ACL scoped.

- `RAGInteraction`: trace/session/turn, pseudonymous subject, query and answer refs,
  model/router/prompt/policy revisions, experiment assignment, answer mode, citations,
  retrieval runs, tokens, cost, cache, latency, error, and residency.
- `RetrievalRun`: KB/index/snapshot/embed/chunker/reranker revisions, query rewrites,
  filters, strategy, top-k, and ordered results.
- `RetrievedItem`: canonical document/version/chunk, content hash, ACL decision, scores,
  rank, freshness/effective dates, duplication group, whether placed in the prompt, and
  truncation reason.
- `Claim`: answer span, normalized proposition and importance, supporting,
  contradicting and cited chunks, verdict, confidence, and evaluator lineage.
- `EvaluationResult`: typed target, canonical metric, value/direction/confidence,
  evidence, evaluator/model/prompt/code revisions, calibration set, sampling reason,
  cost and latency.
- `FrictionEvent`: retry, semantic rephrase, correction, regenerate, feedback, citation
  click/failure, copy, abandonment, escalation, handoff, or manual search; it records
  observed behavior separately from inferred cause.
- `KnowledgeGap`: stable ACL-safe query/claim cluster, frequency/trend, affected cohort,
  failed evidence, suspected cause, severity, confidence, owner and lifecycle.
- `KBChangeProposal`: related gaps, exact proposed change, candidate-source provenance,
  license, owner, expected affected queries, risk, evaluation, approvals, rollout, and
  rollback.

`EvaluationResult` is evidence, not reward ground truth. Terminal reward, process
reward, deterministic validation, user report, behavioral friction, perceived friction,
and LLM-judge output remain separate typed observations with independent lineage and
uncertainty. Optimizers may not launder a weak proxy into a training label or trade away
a hard privacy, safety, entitlement, or critical-slice floor.

## Failure and friction taxonomy

Classification is multi-label and evidence-bearing:

1. Intake or intent misunderstanding.
2. Missing, stale, conflicting, inaccessible, or badly parsed knowledge.
3. Retrieval miss, ranking miss, duplicate/noisy context, or ACL filtering.
4. Context assembly failure: useful evidence retrieved but truncated or not presented.
5. Evidence-utilization failure: useful presented evidence ignored or contradicted.
6. Ungrounded, factually wrong, incomplete, irrelevant, or overconfident generation.
7. Citation invalidity, incorrect entailment, incompleteness, or entitlement leakage.
8. Incorrect abstention, refusal, tool use, trajectory, or authorization behavior.
9. Latency, availability, cost, quota, client, or interaction-design friction.

Retries and thumbs-down are weak labels. Network errors, deliberate exploration, and
healthy clarifying questions can resemble failure. The classifier stores confidence and
evidence; humans validate consequential cases and evaluator calibration.

### Perceived friction is a separate construct

Behavioral friction is observed; perceived friction is reported by the user. Do not
infer the latter solely from retries, rephrases, latency or abandonment. Add voluntary,
low-burden experience sampling at appropriate moments with versioned instruments for:

- disruption and effort burden;
- cognitive load and difficulty deciding what to say or do next;
- loss of control, override difficulty and approval fatigue;
- confidence that the system understood intent and had the right context;
- usefulness of clarification or review, satisfaction and willingness to reuse;
- whether a pause/checkpoint felt protective, educational, unnecessary or obstructive.

Link responses to sanitized interaction and policy revisions, never employee performance
scoring. Use randomized sampling, honor opt-out, cap prompt frequency and measure the
measurement burden itself. Calibrate behavioral proxy models against these reports by
task/cohort without exporting raw conversation content. Preserve disagreement: low
latency can still feel confusing, and high measured effort can be productive.

Experiments report perceived friction beside verified outcome, decision quality,
calibrated reliance, recovery, human agency, latency and cost. The goal is not universal
minimization; it is removing accidental friction while retaining evidence-backed
productive friction for consequential actions.

## Metrics that must remain distinct

- With labeled relevant evidence: Recall@K, Precision@K, Hit@K, MRR, NDCG, MAP,
  document-version correctness, and ACL leakage. Without a known relevant set, never
  call judged relevance "recall."
- Claim coverage: reference claims supported by retrieved evidence, plus rank/time to
  first support.
- Context utilization: relevant prompt evidence actually used for answer claims. High
  retrieval quality plus low utilization identifies prompt/model overload.
- Faithfulness/groundedness: generated factual claims supported by supplied evidence;
  contradiction is separate. A true claim absent from supplied evidence remains
  ungrounded.
- Factual correctness, answer relevance, completeness, concision, and instruction
  following are separate from grounding.
- Citation correctness/entailment, completeness, resolvability, freshness, and
  entitlement safety are separate measures.
- Answerable/unanswerable sets measure false answers, false abstentions, abstention
  precision/recall, and selective risk/coverage.
- Operational measures include stage p50/p95/p99, TTFT, tokens, cost, cache, retries,
  fallbacks, and cost per friction-free resolution.

Framework-native results are retained beside normalized `EvaluationResult` rows.
Adapters include RAGAS, DeepEval, TruLens, Phoenix, Langfuse, LangSmith, RAGChecker,
ARES, Giskard, Promptfoo and NeMo Evaluator. A universal score is not created.

## Execution tiers

### Inline

Only deterministic, bounded checks run on the request path: empty retrieval, score
margin, stale/unauthorized chunks, duplicates, context overflow, citation resolvability,
known forbidden claims, budget, and latency. Policy can answer, clarify, abstain, or
escalate. Inline evaluation has an explicit latency budget and fail-open/fail-closed
policy by check.

### Nearline

Asynchronous seconds-to-minutes evaluation samples document relevance, claim support
and contradiction, citations, utilization, answer usefulness, and judge disagreement.
Errors, abstentions, regulated/high-value traffic, low margins, and friction are sampled
aggressively; a random baseline prevents selection blindness.

### Offline and release

Frozen datasets run reference-backed IR metrics, counterfactual no-context/removed-
context/noise tests, evaluator suites, adversarial probes, confidence intervals, and
paired baseline/candidate slice comparisons. Identical dataset/config/seeds are required
for side-by-side claims.

## Alerts and drift

Alerts require minimum sample sizes and a stable or rolling baseline, and are sliced by
tenant, query cluster, KB/index revision, model, prompt, and router revision.

- Page on ACL/citation entitlement leakage, deleted-source citations, false-answer risk
  spikes under weak evidence, or severe availability/latency failures.
- Open incidents for post-release retrieval/claim-coverage regression, grounding or
  citation floors, high relevance with low utilization, false abstention growth, and
  cost per friction-free resolution regression.
- Track query-embedding and low-density clusters, source distribution, score margins,
  document freshness, contradictions, answer/abstention mix, and evaluator calibration.
  Never page on a raw judge mean alone.

## Knowledge-gap remediation

1. Cluster empty retrieval, low-density queries, unsupported critical claims, user
   corrections, and repeated friction without crossing tenant or ACL boundaries.
2. Produce an evidence-backed root-cause hypothesis: source gap, stale/conflicting
   source, parsing, metadata/ACL, chunk/index/reranker, prompt, model, or tool.
3. For a knowledge cause, create a `KBChangeProposal` with source provenance, exact
   diff, owner, impacted queries, privacy, residency, and license checks.
4. A domain owner reviews it; deletion, ACL, security, and regulated changes require two
   people. Rejections become labeled evaluator/classifier evidence.
5. Build an immutable shadow snapshot and replay frozen regressions plus the affected
   cluster. Check unrelated-query regressions, latency, and cost.
6. Shadow, then tenant-scoped canary. Promote an immutable snapshot only when gates
   pass; retain instant rollback and historical document-version lineage.
7. Close a gap only after an observation window shows improved production friction and
   random-sample quality.

## NVIDIA integration boundary

NVIDIA projects strengthen the worker ecosystem, not the synchronous Go binary:

- NeMo Evaluator's target/config/job separation informs `EvaluationTarget`, immutable
  `EvaluationConfig`, and asynchronous `EvaluationRun` records.
- NeMo Agent Toolkit informs row-level evaluator reasoning, trajectory artifacts,
  profiling, timeline, and lifecycle-event outputs.
- NeMo/NeMo-RL remain external Kubernetes GPU workers for SFT, DPO, GRPO, reward-model
  training, and on-policy distillation.
- garak runs pinned, budgeted security suites against ephemeral/canary endpoints.
- Dynamo owns backend KV-aware worker routing and prefill/decode topology. Bifrost owns
  provider/deployment routing, preserves affinity hints, and consumes backend telemetry.
- Model Optimizer can be a pinned external worker for prune, distill, quantize, export,
  and load-test pipelines; every transformation creates a new immutable artifact.
- TensorRT-LLM, NIM, CUDA, model weights, datasets, and NGC images each require separate
  license and redistribution review. No commercial NIM image is bundled in OSS builds.

Autoscaling self-hosted inference uses queue wait, active sequences, KV occupancy,
TTFT, tokens/second, and deadline misses—not CPU alone—and routes away before cold
capacity is considered ready.

## Friction-paper interpretation

The exact recent **perceived user friction** paper remembered by the team is not yet
uniquely identified. It must not be silently substituted with *The Dataset Friction
Framework*, *Drag or Traction*, designed-friction surveys, or the single-user
`friction-guard` paper. Candidate citations remain a research ledger until a title,
author, link or distinctive result resolves the source. No candidate alone is adequate
evidence for production thresholds; thresholds require calibration on our own reviewed
interactions.

The wider 2026 evidence also includes designed/productive friction, the
friction-performance paradox, and the persuasion paradox. Together they require separate
measurement of perceived effort, verified outcome, calibrated reliance, error recovery
and retained human agency; a faster or more trusted interaction is not necessarily a
better one.

## Primary references

- RAGAS metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- DeepEval RAG evaluation: https://deepeval.com/guides/guides-rag-evaluation
- TruLens RAG triad: https://www.trulens.org/getting_started/core_concepts/rag_triad/
- Phoenix retrieval evaluation: https://arize.com/docs/phoenix/evaluation/pre-built-metrics/document-relevance
- Amazon RAGChecker: https://github.com/amazon-science/RAGChecker
- Stanford ARES: https://github.com/stanford-futuredata/ARES
- NVIDIA NeMo Evaluator: https://github.com/NVIDIA-NeMo/Evaluator
- NVIDIA NeMo RL: https://github.com/NVIDIA-NeMo/RL
- NVIDIA Model Optimizer: https://github.com/NVIDIA/Model-Optimizer
- NVIDIA Dynamo router: https://docs.nvidia.com/dynamo/dev/components/router/router-guide
- NVIDIA garak: https://github.com/NVIDIA/garak
- Dataset Friction Framework: https://arxiv.org/abs/2606.23660
- Drag or Traction: https://arxiv.org/abs/2603.27550
