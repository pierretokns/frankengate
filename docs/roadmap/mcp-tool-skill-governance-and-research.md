# MCP, Tool Search, Skill Marketplace, and Agent Governance

## Product boundary

The gateway is the enterprise membrane for tools. It owns catalog authority, dynamic
discovery, authorization, credential delegation, invocation policy, audit, replay,
health, and kill switches. It does not execute arbitrary marketplace skills in gateway
pods, and it does not treat an MCP connection as proof that content or procedures are
authoritative.

A skill is versioned procedural memory: when and how to perform a workflow, which
approved tools it needs, and how success is tested. Facts remain versioned governed
knowledge-base objects referenced by the skill. This prevents volatile corporate facts
from silently becoming stale executable procedure.

## Existing Bifrost substrate

The current tree already contains useful foundations: MCP client/tool lifecycle, agent
loops, per-user OAuth and header credential resolution, OAuth issuance/refresh rotation,
virtual-key and per-request tool filtering, approval schemas, connected-session
revocation, MCP tool logs, and OpenAI-compatible MCP response types.

The missing enterprise layer is a signed, distributed, continuously reviewed registry;
group/purpose policy; deferred tool discovery; parameter and egress controls; attenuated
credentials; mutation detection; risk approvals; result tainting; conformance; and
trajectory evaluation.

## Registry and marketplace model

Catalog scope is `organization → team/group → user → agent`. Four decisions remain
separate: visible, discoverable, installable, and invocable. A tool returned by search is
not thereby authorized.

Each server, tool, and skill has an immutable signed manifest containing:

- publisher identity, source, digest, version, license, SBOM, dependencies and build;
- owner/reviewer, lifecycle, expiry, attestation and exception ticket;
- declared network, filesystem, secret, identity, region and residency capabilities;
- input/output schemas, examples, idempotency and side-effect classification;
- deterministic tests, security evidence, health SLO and rollback revision;
- for skills: triggers, required tool grants, workflow, positive/negative examples,
  changelog, and governed KB references.

Lifecycle is draft, sanctioned, tolerated-with-restrictions, quarantined, prohibited,
deprecated. A digest, schema, description, capability, dependency, owner, endpoint, or
scope change creates a diff and can force quarantine/reapproval. This addresses
post-approval rug pulls.

## Tool catalog virtualization

Expose one always-visible `tool_search` capability and a small pinned set. Other tools
are `defer_loading` candidates. The catalog supports name-only, summary, and full-schema
expansion; server-level defaults with tool overrides; aliases and collision quarantine;
and hybrid lexical/dense retrieval.

The order is mandatory:

1. Compile identity, group, purpose, data-class, region, and lifecycle authorization.
2. Search only authorized metadata in the pinned catalog snapshot.
3. Rank by relevance plus trust/risk, health, locality, latency, and cost.
4. Return minimal definitions and expand the selected immutable digests.
5. Re-check invocation authorization and parameter policy at call time.

Audit the search query/hash, catalog and policy revisions, filtered and ranked
candidates, scores/reasons, definitions loaded, chosen call, and downstream outcome.
Cache keys include catalog and policy versions. Measure authorized recall@k, definition
tokens, downstream task success, false-tool and unnecessary-tool rates—not similarity
alone.

Compatibility adapters preserve Anthropic deferred loading/tool references, OpenAI
client-executed tool search and MCP lifecycle events, Google thought/tool IDs and
signatures, and provider/model-specific tool dialects. A native Bifrost search surface
is the portable fallback.

## Invocation governance membrane

- Normalize names and quarantine collisions or preference-manipulating descriptions.
- Scan descriptions, examples, schemas, dependencies and responses for injection,
  poisoning, secrets, malware and policy violations.
- Apply strict schema plus parameter ABAC: URI/path/SQL/egress constraints, redaction,
  fanout, timeout, result size, rate/cost, idempotency, and dry-run.
- Classify read, write, destructive, financial, communication, identity/security, code,
  browser/GUI and privileged actions. Consequential operations require risk-based human
  or pre-approved policy authorization.
- Broker short-lived, audience- and scope-bound per-call credentials. Never forward the
  caller's bearer token by default and never persist credentials in traces.
- Treat results as untrusted observations with provenance, taint, DLP, and entitlement
  labels. Returned instructions cannot grant authority or invoke another tool.
- Enforce failover handlings, tenant/server/tool kill switches, concurrency and budgets.

Computer-use, shell, code, image-region and browser actions are typed protocols with
sandbox/environment identity and replay semantics; they are not flattened into generic
JSON functions.

## Distributed MCP control plane

Aurora PostgreSQL remains durable authority for registry and grants. The same outbox,
cursor, wakeup and immutable-snapshot pattern used by identity/policy distributes
catalog revisions to every pod within the 1–5-second revocation target. Pods track
server capability/health diffs, drain changed connections, invalidate catalog caches,
and preserve region affinity/failover. Redis is optional, not mandatory.

## Trajectory and evaluation contract

Every episode records catalog retrieval candidates/scores, definition digest, model and
provider revisions, arguments (redacted reference plus hash), auth and approval receipt,
call/result IDs, result provenance, retries/errors/cancellation, side effects or world-
state diff, whether evidence was used, and step/terminal reward, tokens, cost, TTFT and
latency.

Replay modes include exact stubbed, live shadow, counterfactual model/router/catalog,
and adversarial MCP servers. Gates cover:

- tool needed, authorized recall@k, selection, hallucinated/unnecessary calls;
- argument schema and semantic correctness, ordering/dependencies and result use;
- multi-turn recovery, pass^k/reliability, latency, cost and policy violations;
- prompt/retrieval injection, poisoned descriptions, name collision, rug pull,
  confused deputy, impersonating responses, covert calls and permission leakage;
- deterministic database/world-state changes for transactional tasks.

Use BFCL, tau-bench, MCP-Atlas, TRAJECT-Bench, ToolRet, ToolACE, ToolSandbox,
MCP-AgentBench and domain packs as inspiration/adapters. Preserve native formats and
licenses; protocol conformance and answer quality remain separate. Noncommercial
datasets, including FinMCP-Bench under its reported CC-BY-NC-SA terms, cannot enter a
commercial training corpus without permission.

Reviewed traces can create retrieval, invocation, argument-repair, error-recovery and
process-reward datasets. Model-generated or raw user trajectories are never ground
truth; deterministic verification, human adjudication, lineage, leakage checks, offline
evaluation, shadow/canary and rollback apply.

## ASPIRE-inspired self-improving skills

NVIDIA GEAR's 2026 ASPIRE paper is the robotics work intended here. Its transferable
pattern is: fine-grained per-primitive traces → causal failure localization → candidate
program repairs → re-execution → validated fixes → reusable skill library → retrieval
on later tasks. It also uses parallel/evolutionary exploration rather than accepting a
single repair trajectory.

For enterprise agent workflows, the corresponding loop is:

1. Detect a repeated friction/failure or a high-value successful recovery across tool
   search, planning, invocation, validation and outcome spans.
2. Create a `SkillGapCase` with the causal chain and counterevidence. Distinguish tool
   selection, authorization, parameters, stale procedure, missing precondition,
   environment drift, result interpretation and recovery.
3. Generate multiple `SkillChangeProposal` candidates: description/example improvement,
   precondition, tool substitution, parameter validator, recovery branch, decomposition,
   new skill, merge, split, or retirement. Candidates cannot publish themselves.
4. Run each candidate in a deterministic sandbox against the implicated replay cluster,
   the full regression pack, adversarial cases, and held-out task/environment slices.
5. Compare paired success, policy violations, tool calls, retries, tokens, cost, latency,
   and unrelated-task regressions. Require executable outcome validators; an LLM judge
   alone is insufficient.
6. A skill owner reviews provenance, exact diff, evidence, required permissions and
   rollout. High-risk or cross-tenant changes require two people.
7. Publish an immutable candidate, shadow it, then sticky-canary by approved cohort.
   Automatically roll back on policy or quality gates and only close the gap after a
   production observation window.
8. Promote the reviewed repair pattern—not raw customer traces—into reusable procedural
   memory. Preserve tenant boundaries and require explicit policy for cross-tenant
   aggregation or transfer.

Required records are `SkillGapCase`, `SkillChangeProposal`, `SkillExperiment`,
`SkillRevision`, and `SkillPromotionReceipt`. Every candidate records parent revision,
trigger traces, sanitized evidence, author model/prompt, exact diff, tool/catalog/policy
and environment revisions, validator/evaluator revisions, experiment statistics,
approvals, canary and rollback.

The robotics analogy also exposes limits that become product requirements. ASPIRE notes
that success detection and safety calibration remain hard, its frontier-model/search
loop is expensive, its primitive API bounds what can be learned, and a growing library
can become stale, redundant, overly specific or misleading. Therefore the marketplace
needs expiration, duplicate/conflict detection, specificity and portability scores,
budgeted proposal generation, archive/retirement, and periodic held-out revalidation.

The initial feature is **suggested skill evolution**, not autonomous self-modification.
Tenant-approved low-risk auto-promotion may be considered only after calibrated outcome
validators, a long audit history, bounded permissions, automatic rollback and explicit
policy exist.

### Skill effectiveness and compounding leverage

Evaluate a skill revision as a production dependency across a matrix, not with one
aggregate pass rate:

- task family, team/tenant, agent harness, model/provider/version, reasoning effort,
  tool/catalog/policy revision, environment, data shape and difficulty slice;
- first-pass success, pass^k/reliability, partial progress, recovery, regression and
  abstention/escalation;
- unnecessary/wrong calls, argument/ordering/result-use correctness, human edits,
  policy/security violations and side-effect rollback;
- wall time, TTFT, calls, retries, tokens, evaluator and inference cost, and cost per
  verified successful outcome;
- transfer to held-out tasks, models and teams, plus specificity, freshness, duplicate
  overlap and negative-transfer rate.

Report paired baseline/candidate deltas with confidence intervals and critical-slice
floors. Weight impact by invocation volume and business criticality to estimate
`expected_downstream_value`, but never allow high volume to hide a security regression.
Track attribution carefully: skill selection, skill content, model, tool, environment and
policy can all cause the outcome. Randomized sticky experiments or matched replay are
preferred to naive before/after dashboards.

Maintain a dependency graph from skill revision to child skills, tools, linters, models,
teams and workflows. This provides blast-radius estimates, revalidation fanout and a
rollup of saved failures, tokens, wall time and cost. It also identifies high-leverage
skills where a small verified improvement compounds across a software-development dark
factory or Jira-to-merge workflow.

### Graduating prose into deterministic tools

Repeated procedural reasoning should be mined for deterministic seams. For example, a
SQL review skill can call versioned parsers and policy packs for DDL/DML classification,
dialect-aware lint, migration safety, lock/rewrite risk, destructive statement checks,
parameterization, privilege/tenant predicates, EXPLAIN/plan regressions and organization
code smells. The skill retains orchestration, intent and escalation; the tool returns
structured findings with rule ID/version, source spans, evidence, severity, confidence
and fix safety.

A `DeterminizationProposal` is created when a step is frequent, costly, inconsistently
judged, mechanically specifiable, or safety-critical. It includes extracted examples,
counterexamples, a proposed tool contract, golden/metamorphic/fuzz tests and an estimate
of precision/recall, latency and cost. Promotion requires differential validation against
reviewed cases and shadow execution. New rule-pack versions are immutable dependencies
and trigger skill revalidation; false-positive/false-negative feedback proposes rule
updates through the same governed loop.

Reasoning effort becomes an experimental treatment. Compare a cheap model plus strong
deterministic primitives against a stronger model, and use a cascade when confidence or
validator disagreement demands escalation. Optimization targets verified outcome under
latency/cost and safety constraints—not cheapest invocation or highest judge score.

## Wider model and serving capabilities

Current U.S. and Chinese lab work reinforces two versioned records:

- `ModelCapabilityManifest`: artifact/tokenizer/template/parser hashes and licenses;
  modality/context; reasoning mode; tool dialect; parallel/strict calls; logprobs;
  cache semantics; quantization; engines; residency; dated benchmark evidence.
- `ServingEndpointManifest`: backend build, accelerator/topology, prefill/decode role,
  KV format/cache domain, parser/template, capacity, TTFT/tokens-per-second/cost and
  health.

These support explicit parameter-translation ledgers, reasoning-channel privacy,
prefix-cache compatibility probes, long-context-versus-RAG routing, topology-aware
capacity, quantization-specific canaries, and parser/vendor conformance. Kernels from
DeepSeek, Qwen, Kimi, GLM, MiniMax, Hunyuan, ERNIE, UI-TARS, AgentCPM, LMDeploy or
NVIDIA remain in their engines/workers; the gateway normalizes and governs them.

## Hermes comparison and memory-index boundary

Hermes adds two useful, but non-authoritative, patterns to this design: progressive
disclosure of skill metadata before loading a full skill, and a post-turn curator that
can draft or revise skills from observed work. Its evolutionary self-improvement work
also explores DSPy/GEPA-style candidate optimization, while its learning-loop
documentation points to trajectory-based RL. These are proposal-generation and
experiment techniques, not permission to mutate the approved marketplace. FrankenGate
must retain immutable revisions, deterministic validators, held-out regression packs,
human/MR approval, sticky canaries and rollback for every candidate.

History storage is deliberately split by authority and purpose. Store only a
privacy-filtered evidence envelope (tenant, purpose, retention, pseudonymous subject,
tool/model metadata, redacted text and outcome facts); never use raw prompts, outputs or
tokens as a general learning corpus. SQLite/CASS-style lexical history is the simplest
authoritative per-user/team recall layer. Aurora owns durable policy, ownership,
retention, deletion and audit state. A vector index (pgvector, Qdrant or another
adapter) may be built as a rebuildable, tenant-scoped derived index for similarity and
friction clustering, but it cannot authorize access, satisfy deletion by itself, or
become the semantic-cache authority. Every index entry carries the source envelope,
purpose and revision so it can be revoked and rebuilt after policy changes.

Code, model weights, tokenizer/template, datasets, derived quantizations and containers
each have independent license/provenance entries. OpenAI compatibility and a research
paper grant neither behavioral equivalence nor implementation rights.

## Prioritized delivery

1. Canonical trace/replay and policy receipt.
2. Signed tenant-scoped catalog, lifecycle and authorized deferred discovery.
3. Credential broker, invocation firewall, result trust boundary and kill switches.
4. Adversarial MCP and multi-turn trajectory conformance packs.
5. Approved skill marketplace manifests and external sandbox runners.
6. Provider/model tool-dialect and parser/template registry.
7. Search/retriever learning from reviewed outcomes.
8. Pure/read-only tool-flow parallelism and speculation only after replay evidence.

## Primary references

- Anthropic advanced tool use: https://www.anthropic.com/engineering/advanced-tool-use
- Anthropic code execution with MCP: https://www.anthropic.com/engineering/code-execution-with-mcp
- Anthropic MCP directory policy: https://support.anthropic.com/en/articles/11697096-anthropic-mcp-directory-policy
- OpenAI Responses MCP support: https://openai.com/index/new-tools-and-features-in-the-responses-api/
- Google tool combinations: https://ai.google.dev/gemini-api/docs/tool-combination
- Qwen-Agent: https://github.com/QwenLM/Qwen-Agent
- ToolRet: https://arxiv.org/abs/2503.01763
- MCP-Atlas: https://arxiv.org/abs/2602.00933
- MCP Security Bench: https://arxiv.org/abs/2510.15994
- MCP threat modeling/tool poisoning: https://arxiv.org/abs/2603.22489
- ShareLock multi-tool poisoning: https://arxiv.org/abs/2606.27027
- Berkeley BFCL: https://gorilla.cs.berkeley.edu/leaderboard.html
- tau-bench: https://github.com/sierra-research/tau-bench
- Amazon TRAJECT-Bench: https://www.amazon.science/publications/traject-bench-a-trajectory-aware-benchmark-for-evaluating-agentic-tool-use
- Meta Toolformer: https://ai.meta.com/research/publications/toolformer-language-models-can-teach-themselves-to-use-tools/
- NVIDIA ASPIRE: https://research.nvidia.com/labs/gear/aspire/
- Hermes skills: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/
- Hermes learning loop: https://hermes-agent.ai/features/learning-loop
- Hermes self-evolution: https://github.com/NousResearch/hermes-agent-self-evolution
