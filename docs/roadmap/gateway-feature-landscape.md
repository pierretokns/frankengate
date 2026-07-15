# AI Gateway Feature Landscape

Status: history-recovered and primary-source-verified research, 2026-07-14

## History recovered from State of AI

The prior State of AI work emphasized a platform boundary rather than a thin proxy:

- LiteLLM, Portkey and Helicone as the principal gateway comparison set.
- PrivateLink/VPC endpoints, Redis token-bucket team limits, semantic caching,
  cross-region least-loaded/cheapest routing, sampled logging and key-to-CUR attribution.
- Bedrock Application Inference Profiles and request metadata for attribution; Cost and
  Usage Reports are reconciliation, not per-request routing truth.
- An SCP pattern that denies direct `bedrock:InvokeModel` except through the gateway
  role, preventing governance and cost-attribution bypass.
- Model-tier routing using token length, tool use and complexity.
- Three log tiers: complete metrics, complete metadata-only events, and policy-sampled
  encrypted payloads in compressed object storage.
- Geographic/global Bedrock cross-region profiles by default; custom region routing only
  where explicit order, cross-provider fallback, evidence or policy requires it.
- Semantic-cache TTL and similarity thresholds must be category-aware, include embedding
  cost, and be invalidated when DLP/guardrail/policy semantics change.

Prime/Hugging Face replay, RL trajectory branching and logprob normalization were not
meaningfully present in the recovered history; those are new research, not remembered
decisions.

## Competitive behavior worth implementing

### Cloudflare AI Gateway

Its dynamic-routing JSON is a useful behavioral reference for a versioned route DAG:
conditional nodes, percentage splits, limits, endpoints and fallbacks. Other strong
patterns are configurable retry/backoff, payload-free logging with metrics, exact-hash
cache keys, and explicit DLP/cache interaction.

Requirement: route policies are immutable/versioned, validated before activation,
atomically swapped, explainable per request and capability-gated.

Sources:

- https://developers.cloudflare.com/ai-gateway/features/dynamic-routing/json-configuration/
- https://developers.cloudflare.com/ai-gateway/observability/logging/
- https://developers.cloudflare.com/ai-gateway/features/caching/
- https://developers.cloudflare.com/ai-gateway/features/dlp/

### Portkey

Behavioral references include recursively nested load-balance/fallback/conditional
strategies, status-code-scoped failover, canary weights and inference parameter pass-
through. Treat public documentation as requirements unless exact source paths pass the
provenance gate.

Sources:

- https://portkey.ai/docs/product/ai-gateway/fallbacks
- https://portkey.ai/docs/product/ai-gateway/conditional-routing
- https://portkey.ai/docs/product/ai-gateway/canary-testing

### Envoy AI Gateway

Apache-2.0 reference for Kubernetes Gateway API/CRDs, global authentication/rate limit,
fine-grained inference endpoint selection, status reporting, model-name rewriting and
two-tier gateway topology. It is stronger as a Kubernetes/data-plane reference than as
an experiment or replay product.

Source: https://github.com/envoyproxy/ai-gateway

### TensorZero

Apache-2.0 and the strongest open reference for the gateway-to-learning flywheel:
historical replay, datasets, evaluations, optimization, adaptive A/B experiments,
sequential testing, feedback and multi-turn experiments.

Source: https://github.com/tensorzero/tensorzero

### Kong and OpenRouter

Useful behavior includes round robin, consistent hash/stickiness, latency/usage and
semantic selection; ordered providers; required-parameter eligibility; zero-data-
retention and training-policy filters. Advanced Kong routing is proprietary and
OpenRouter is a service, so these are clean-room behavior references only.

Sources:

- https://developer.konghq.com/ai-gateway/load-balancing/
- https://openrouter.ai/docs/guides/routing/provider-selection

### LiteLLM

Useful test-oracle areas include virtual keys/teams, Postgres persistence, Prometheus,
Kubernetes HPA/PDB, fallback and cost routing. Prior history also recorded a proxy
throughput regression report; no algorithm should be ported without benchmarking
Bifrost and auditing the exact stable file license.

Sources:

- https://docs.litellm.ai/docs/proxy/prod
- https://docs.litellm.ai/docs/proxy/virtual_keys
- https://github.com/BerriAI/litellm/blob/main/deploy/kubernetes/kub.yaml

### Semantic and learned routers

The vLLM Semantic Router and Aurelio Semantic Router demonstrate intent/complexity/tool
classification, embedding-nearest routes, multimodal and hybrid routes, persistence and
threshold fitting. Not Diamond demonstrates a feedback-bearing decision ID and custom
routers trained from evaluation data. Hard governance filters stay outside all learned
scoring.

Sources:

- https://github.com/vllm-project/semantic-router
- https://github.com/aurelio-labs/semantic-router
- https://docs.notdiamond.ai/docs/what-is-model-routing

## Bedrock and Mantle

`bedrock-mantle` is a real newer regional Bedrock endpoint and service namespace, not
a cross-region failover system. It supports OpenAI-compatible APIs and Anthropic
Messages, with Projects/Workspaces for isolation, access and cost organization.
The gateway target model must distinguish ordinary runtime model IDs, Mantle project or
workspace targets, system cross-region profiles, application inference profiles and
Provisioned Throughput ARNs.

Bedrock cross-region inference offers geography-constrained or global AWS-managed
routing. Destination selection is opaque: it does not expose customer weights, explicit
order, health score or stickiness. Record actual processing region, policy/profile and
route evidence. Validate every profile destination against IAM/SCP and data residency.

Important details:

- Global profiles prioritize the broadest capacity; geographic profiles constrain the
  destination set to a geography.
- Application Inference Profiles primarily add model-specific tagging/cost attribution;
  they are not arbitrary multi-model routers.
- Provisioned Throughput and inference profiles are distinct capacity pools.
- Prompt caching is model/API-specific; cache routing can increase cache writes and
  should be measured rather than assumed region-affine under CRIS.
- Model TPM admission must account for documented output-token burndown, which is quota
  accounting rather than billing.
- Bedrock Guardrails can have a separate cross-region inference profile; model and
  guardrail processing residency must both be evaluated and recorded.
- Once streaming bytes have been returned, silent failover is prohibited by default.

Sources:

- https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-cross-region-support.html

## Constraint-first routing

Candidate selection must filter before scoring:

1. Identity, virtual-key, team and access-profile entitlement.
2. Operation and model capabilities: context, modality, tools, structured output,
   prompt/output logprobs, logit bias, streaming and batch.
3. Geography, residency, zero-retention, training and guardrail policy.
4. Endpoint health, circuit state, quota/capacity and tenant budget.
5. Only then rank by policy priority, cost, latency/TTFT, least-busy, cache affinity,
   semantic match, quality prediction or learned feedback.

The route record contains every considered candidate, rejection code, score inputs,
selected endpoint, attempt tree and actual provider/region evidence.

## Logprobs and logit controls

Normalize provider-native output without destroying it: token text and bytes, token
logprob, top alternatives, rank, position and finish reason. The capability registry
distinguishes unsupported, unavailable, omitted and policy-redacted values; prompt and
output support; unary and streaming support; and maximum `top_logprobs`.

Do not compare raw probabilities across tokenizers as if they were calibrated. Pass
`logit_bias` only when provider/tokenizer semantics are compatible; otherwise reject it
clearly instead of silently dropping it. Treat logprob arrays as sensitive, high-volume
payloads with explicit retention and replay policy.

Uses include uncertainty signals, evaluator features, token-level debugging, constrained
generation diagnostics, router training and RL policy-gradient datasets. They must not
be presented as factual confidence without calibration.

## Replay, evaluation and RL environment flywheel

The immutable inference envelope captures normalized/raw request policy tier, tools and
schemas, principal/tenant, prompt/route revisions, provider/model/region, sampling and
seed, attempt tree, timing, usage/cost, output/error, feedback and trace links.

Replay modes:

- Exact-input counterfactual re-execution; never promise bit identity.
- Transformed replay after prompt/tool/schema migration.
- Shadow replay against a candidate route with no caller-visible response.
- Batch dataset replay with paired diffs and versioned evaluators.
- Tool policy: off, recorded stub, sandbox, allowlist, or explicitly approved live.

The RL trajectory is a tree/DAG: environment and policy versions, reset seed/state,
observations, actions/tool calls, per-turn token logprobs, component rewards,
termination/truncation, parent/branch point, sandbox provenance and timings.

Prime Intellect Verifiers provides task+harness+rubric environments, trajectory
tracking, branching/truncated/resumed rollouts, eval and training package reuse. PRIME-
RL supplies an Apache-2.0 asynchronous training reference. Hugging Face OpenEnv supplies
a container-first HTTP reset/step/state contract and TRL integration. These workers run
outside the gateway hot path through a separately admitted rollout queue.

Sources:

- https://github.com/PrimeIntellect-ai/verifiers
- https://github.com/PrimeIntellect-ai/prime-rl
- https://huggingface.co/docs/openenv/index
- https://huggingface.co/docs/trl/openenv

## Identity flywheel

Identity is part of the learning and governance loop, not just login:

`IdP group/claim -> role/team/profile -> virtual key and hard capabilities -> route and
data policy -> trace attribution -> cost/quality/safety feedback -> reviewed profile or
router revision -> canary -> audited promotion`.

Raw feedback never grants access automatically. Hard entitlements and residency remain
human-governed. Learned routing can optimize only inside the eligible set. Every dataset
and evaluator is tenant-scoped and provenance-tagged; deprovisioning applies to future
access and retention policy without corrupting immutable audit evidence.

## Additional backlog candidates

- Prompt registry/versioning with immutable hashes and environment promotion.
- Provider capability discovery with scheduled drift alerts.
- Route-policy simulator and explain-decision API before activation.
- Quota headroom prediction and limit-increase workflow.
- Cache-affinity routing with DLP/guardrail revision invalidation.
- Per-feature/product/use-case cost attribution, not only team totals.
- SCP/IAM policy generator that prevents direct-provider governance bypass.
- Privacy-tiered logs and payload sampling.
- Signed route evidence binding policy revision, selected target and attempt result.
- Adapter conformance kit for OpenAI/Anthropic/Bedrock/Mantle streaming, tools,
  structured output, logprobs and errors.
- Governed `LearningDataset`, `TrainingJob` and `ModelArtifact` resources feeding
  external Unsloth/TRL/Prime/OpenAI/DSPy workers.
- Behavioral-output, preference/reward, router/prompt and optional logit distillation as
  distinct pipelines with immutable teacher/student provenance.
- Blind side-by-side teacher/base-student/trained-student comparison with repeated
  samples, slice analysis, human annotation and confidence-aware promotion.

## Competitor issue signals and differentiators

Current GitHub backlogs reveal failure modes that marketing feature matrices miss:

- **Policy-monotonic fallback:** Bifrost issue 4243 reports virtual-key provider
  restrictions bypassed through a model-catalog fallback. Every retry, fallback, alias,
  catalog and replay path must prove that candidate sets only narrow after governance.
  Source: https://github.com/maximhq/bifrost/issues/4243
- **Unambiguous hierarchical budgets:** LiteLLM issues 11083 and 12905 show end-user
  budget bypass and surprising team-versus-user semantics. Bifrost needs explicit budget
  algebra and a machine-readable decision receipt.
  Sources: https://github.com/BerriAI/litellm/issues/11083 and
  https://github.com/BerriAI/litellm/issues/12905
- **Quota-aware failover:** Envoy AI Gateway issue 1571 asks for token quotas with
  failover. Reservations/refunds must prevent double charging and exhausted targets
  must be removed before retries.
  Source: https://github.com/envoyproxy/ai-gateway/issues/1571
- **Replay security:** vLLM Semantic Router issue 1146 requests authentication and
  network controls for replay. Replay requires purpose-scoped RBAC, encrypted/redacted
  content, egress policy, tool sandboxing, immutable audit and retention/deletion.
  Source: https://github.com/vllm-project/semantic-router/issues/1146
- **Retrieval/difficulty routing:** vLLM Semantic Router issues 155 and 1166 request
  retrieval-aware and calibrated difficulty routing. Learned routers require OOD and
  confidence evaluation, offline replay scoring and a safe baseline fallback.
  Sources: https://github.com/vllm-project/semantic-router/issues/155 and
  https://github.com/vllm-project/semantic-router/issues/1166
- **Credential delegation:** Envoy AI Gateway issue 1966 highlights forwarding original
  authorization to MCP backends. Bifrost must distinguish caller identity, gateway
  workload identity and narrowly delegated downstream credentials; tool parameters
  require an outbound policy firewall.
  Source: https://github.com/envoyproxy/ai-gateway/issues/1966
- **Pricing correctness:** Helicone issue 5690 reports tiered-pricing failures. Cost
  displays must derive from a versioned pricing ledger and conformance fixtures rather
  than ad-hoc dashboard calculations.
  Source: https://github.com/Helicone/helicone/issues/5690
- **Provider compatibility:** Portkey issue 463 demonstrates logprobs compatibility
  gaps, reinforcing capability-negotiated pass-through and conformance testing.
  Source: https://github.com/Portkey-AI/gateway/issues/463

Issue popularity is prioritization evidence, not proof that a proposed design is
correct. Closed issues may be useful regression specifications; open issues remain
unverified reports until reproduced.
