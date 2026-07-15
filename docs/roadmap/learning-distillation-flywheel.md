# Governed Learning and Distillation Flywheel

Status: architecture and backlog input
Date: 2026-07-14
Scope: internal U.S.-only research on Kubernetes

## Product boundary

Bifrost is the control plane and evidence spine for learning from inference. It is not
a GPU training runtime. The gateway captures governed traces, compiles immutable
datasets, runs evaluations and side-by-side comparisons, submits external training
jobs, registers artifacts, routes canaries, and promotes or rolls back candidates.

Unsloth, Hugging Face TRL, Prime, OpenAI, and later training systems run behind adapters
in isolated workers. No PyTorch/CUDA dependency or arbitrary grader/tool execution is
allowed inside the latency-critical gateway or control-plane process.

## End-to-end loop

`governed inference -> privacy-tiered trace -> feedback/annotation -> immutable dataset
snapshot -> baseline evaluation -> prompt/router/model candidate -> external training or
optimization -> artifact registration -> paired replay -> shadow -> sticky canary ->
audited promotion/rollback -> new governed traces`.

Identity remains attached throughout. Every trace, example, annotation, evaluator,
experiment, job, artifact and promotion references immutable subject/team/service
identity and the effective group-derived policy version. Content stores use pseudonymous
research subject IDs; the re-identification map is separately protected.

Purpose-scoped grants are distinct: `observe`, `annotate`, `replay`, `export-training`,
`launch-job`, and `promote`. Inference permission never implies training-data export.
Okta group removal changes future access immediately without rewriting historical audit
provenance.

## Trace capture tiers

1. `metadata_only`: route, policy, model, timing, tokens, cost and errors; no content.
2. `redacted_content`: content after versioned PII/secrets/DLP transformations.
3. `encrypted_full`: full content under a research-specific encryption and retention
   policy; never automatically training-eligible.
4. `training_eligible`: explicit purpose/consent and license/terms checks in addition to
   content controls.

Each trace records inference, trace, evaluator, replay and training egress residency
separately. U.S.-only policy rejects global Bedrock profiles and non-U.S. collectors or
training endpoints. Missing region metadata fails closed for export/training.

## LearningDataset

An immutable dataset snapshot contains:

- ID, version, parent snapshot and content hash.
- Source trace query, time bounds and route/policy revisions.
- Tenant/research purpose, consent/legal basis and retention.
- Redaction/scanner versions and deletion tombstones.
- Schema: `sft`, `preference`, `prompt_only`, `trajectory`, `vision`,
  `behavioral_distillation`, or `logit_distillation`.
- Train/development/test split seed and immutable memberships.
- Leakage-group keys that keep near-duplicates, sessions and source documents in the
  same split.
- Record hashes and references to encrypted blobs, not copied plaintext.
- Tool-side-effect stripping and recorded/stubbed tool-result policy.
- Teacher, prompt, tokenizer, chat-template and tool-schema provenance.

Compilation performs exact and semantic deduplication, contamination checks, quality
and feedback filters, cohort balancing, license/terms checks, PII/DLP gates and slice
statistics. The holdout is frozen before any optimizer can inspect it.

## Evaluation registry

Evaluators are immutable and content-addressed:

- Type: code/deterministic, LLM judge, pairwise, semantic similarity, trajectory,
  safety, performance/cost or human rubric.
- Exact prompt, response schema, judge model/revision and sampling parameters.
- Code/container digest for executable graders.
- Optimization direction, aggregation and slice rules.
- Calibration dataset, human agreement, confusion matrix/F1 where applicable.
- Cost, latency, timeout/error policy and residency.

Executable graders run only in sandboxed workers with constrained filesystem, network,
time, memory and CPU/GPU. Evaluators are themselves traced. A candidate optimizer cannot
change a production route directly.

## Side-by-side evaluation

Side-by-side comparisons support baseline, teacher, base student, trained student,
prompt variant, router revision and provider target. Use the same immutable dataset,
prompt/tool/template and evaluator revisions wherever the comparison requires it.

Capture:

- Blind randomized pair assignment and reviewer reservations.
- Multiple stochastic samples and seeds.
- Output and tool-trajectory diffs.
- Latency, TTFT, tokens, cache, cost and per-evaluator reward.
- Win/tie/loss, confidence intervals, effect size and critical-slice results.
- Human corrections, annotations, inter-rater agreement and adjudication.
- Failure, refusal, truncation and reward-hacking evidence.

Offline paired replay is distinct from online dual-run/shadow traffic. Online side-by-
side uses deterministic session assignment; side-effecting tools are recorded/stubbed or
sandboxed. The caller receives one designated response only.

## TrainingJob contract

A provider-neutral job includes:

- Method: SFT, DPO, KTO, GRPO, RLOO, RFT, LoRA, QLoRA, behavioral distillation,
  logit distillation or prompt/program optimization.
- Backend adapter: Unsloth, TRL, Prime, OpenAI, DSPy, or future backend.
- Immutable base and teacher model revisions.
- Dataset/evaluator/rubric IDs and frozen split membership.
- Hyperparameters and method-specific schema version.
- Container/code digest, hardware request, runtime/kernel/library versions and secrets
  references.
- Allowed U.S. egress/artifact destinations.
- Events, checkpoints, status, cancellation, retry, cost and output artifact IDs.

Workers consume signed job specs through a queue, fetch secrets through workload
identity, scrub logs, and publish signed results. A seed is recorded for reproducibility,
but GPU/provider output is not promised bit-deterministic.

## Unsloth adapter

Unsloth core is Apache-2.0. Unsloth Studio is AGPL-3.0 and must not be copied or linked
into the Apache fork without a deliberate legal/architecture decision. Model weights,
datasets, notebooks, tokenizers and generated data retain independent licenses.

The adapter generates pinned external worker specs for SFT, LoRA/QLoRA, DPO/GRPO and
supported recipes. Preserve base model, tokenizer/chat template, target modules, rank,
alpha, dropout, bias, quantization, seed, gradient checkpointing, effective batch,
optimizer/scheduler, data snapshot and container digest.

Exports may be adapter-only, merged, vLLM-compatible or GGUF/llama.cpp/Ollama-compatible.
Deployment is blocked unless tokenizer, chat template, BOS/EOS behavior and generation
defaults are immutable artifact metadata. Training/inference template mismatch is a
release-blocking conformance failure.

Sources:

- https://github.com/unslothai/unsloth
- https://docs.unsloth.ai/basics/lora-parameters-encyclopedia
- https://docs.unsloth.ai/basics/saving-and-using-models/troubleshooting

## Hugging Face TRL adapter

TRL is an Apache-2.0 external training plane for SFT, DPO, KTO, reward modeling, RLOO,
GRPO, agent/tool loops, OpenEnv and distillation recipes. Version every generated config
and adapter schema.

Agentic training requires prefix-preserving chat templates: appending tool messages
cannot rewrite the earlier serialized prefix. Bifrost validates this property before an
artifact is eligible for agentic RL.

TRL's DistillationTrainer is experimental. It can express on/off-policy mixtures,
forward/reverse/interpolated KL, external or local vLLM teachers, buffered student
generation, LoRA and compact logprob transfer. Do not expose its unstable API as a
durable Bifrost contract; translate the stable Bifrost job into a versioned adapter.

Sources:

- https://huggingface.co/docs/trl/main/clis
- https://huggingface.co/docs/trl/grpo_trainer
- https://huggingface.co/docs/trl/main/distillation_trainer

## Distillation methods

### Behavioral-output distillation

A frontier teacher produces high-quality outputs. The pipeline filters and curates
those demonstrations, trains a smaller student through SFT/preference/RFT methods, and
compares teacher, base student and trained student on untouched holdout data.

This is the portable default because many hosted APIs expose outputs but not teacher
token distributions. It must record teacher model/revision, prompt/tool/template,
sampling, route/provider, policy and filtering provenance.

### Logit/token-distribution distillation

Where a teacher exposes compatible distributions, train the student against teacher
token probabilities using forward, reverse or interpolated KL. Tokenizer compatibility
is explicit; different tokenizers require alignment or a method that does not pretend
token positions are identical. Logprobs are sensitive, high-volume artifacts with a
separate capture and retention policy.

### Preference and reward distillation

Create chosen/rejected pairs, rubric scores or tool-trajectory rewards. Validate graders
against experts, sample stochastic outputs, monitor reward hacking and noisy labels, and
fix the reward definition before adding compute.

### Router and prompt distillation

Teacher traces can train a small complexity/intent/capability router or optimize prompts
and tool descriptions without changing the response model. These candidates use the
same dataset/evaluator/promotion machinery and can often deliver value before weight
tuning.

## ModelArtifact registry

Each artifact records:

- Base/teacher/dataset/training-job lineage.
- Adapter versus merged weights and quantization.
- Model, weights, tokenizer, dataset and generated-output licenses/terms.
- Tokenizer revision/hash, chat-template body/hash, BOS/EOS and generation defaults.
- Context length and declared capabilities: tools, structured output, modality,
  streaming, logprobs, logit bias and batch.
- File digests, signature, SBOM and vulnerability scan.
- Runtime compatibility: vLLM, TGI, GGUF/llama.cpp, Ollama or provider API.
- Evaluation, critical-slice, safety, latency and cost evidence.
- Deployment aliases/revisions and promotion history.

## Promotion gate

A candidate can progress only when:

1. Provenance, licenses, signatures and scans pass.
2. Holdout aggregate and critical slices meet non-regression thresholds.
3. Safety, privacy, tool and reward-hacking checks pass.
4. Cost/latency/throughput stay within policy.
5. Sample size, confidence/effect thresholds and repeated-run stability pass.
6. Shadow succeeds before deterministic sticky canary.
7. Alert and automatic rollback policies are armed.
8. A permitted human or pre-approved policy signs the promotion decision.

## Open and managed integrations

- OpenInference supplies the canonical OTel-compatible semantic conventions and Go
  masking/attribute substrate: https://github.com/Arize-ai/openinference
- Phoenix is the preferred self-hostable internal default for span-to-dataset,
  experiment replay/comparison and traced evaluators: https://arize.com/docs/phoenix/
- AgentCore provides adapters for trace/session evaluation, dataset runs, immutable
  prompt/tool bundles and managed A/B optimization: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html
- TensorZero remains the strongest Apache-2.0 reference for historical replay,
  experiments, optimization and adaptive routing: https://github.com/tensorzero/tensorzero
- DSPy supplies prompt/program optimizers behind a bounded adapter; preserve trial
  lineage, cost and untouched holdout: https://github.com/stanfordnlp/dspy
- OpenAI Evals/Graders and training remain optional adapters, never the internal source
  of truth. Provider lifecycle changes are one reason to preserve portability.

Production feedback, retrieval evidence, friction classification, alerting, and
knowledge-base change governance are specified in
`docs/roadmap/realtime-friction-rag-quality-plane.md`. Training eligibility consumes
reviewed snapshots from that plane; it never treats raw thumbs-down, retries, or user
corrections as ground truth.

## Launch stages

1. Canonical trace envelope, capture tiers and U.S.-only egress enforcement.
2. Dataset compiler, evaluator registry and offline side-by-side replay.
3. Human annotation/reviewer queues and immutable experiment bundles.
4. Model artifact registry plus shadow/sticky-canary promotion.
5. One external Unsloth/TRL Kubernetes-worker adapter.
6. Behavioral distillation teacher/student pipeline.
7. Optional Prime/OpenEnv trajectory and RL adapters.
8. Optional logit distillation only after capability, tokenizer and retention evidence.
