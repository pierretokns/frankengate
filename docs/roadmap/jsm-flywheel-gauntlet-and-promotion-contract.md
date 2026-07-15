# JSM Flywheel Gauntlet and Promotion Contract

Status: architecture and governance contract; production self-promotion prohibited

## Launch profile: internal Git marketplace

The launch marketplace is internal, and every skill change is merged through the existing Git merge-request workflow with mandatory human approval. Git is therefore the authoritative skill registry and promotion state machine at launch. Skills execute from an immutable commit SHA; the gateway may collect privacy-eligible evidence, create an issue, prepare a patch, or open a draft merge request, but it receives no credential or API path capable of merging, bypassing branch protection, or publishing directly.

This materially reduces the launch system. The required controls are:

- Repository ownership, branch protection, required CI, and at least one authorized human approval.
- A reviewable diff with provenance, declared permissions/dependencies, and no raw private traces.
- Redaction and tenant/user authorization before evidence is persisted or attached to an issue or merge request.
- Sandboxed validation without inherited production, cloud, provider, database, or deployment credentials.
- Deterministic schema/contract tests plus focused end-to-end tests for the capabilities the skill can exercise.
- Deployment pinned to a commit SHA, an audit trail linking evidence to the merge request, and rollback by reverting or pinning the last known-good SHA.

The launch gateway does **not** implement autonomous publication, contextual-bandit promotion, sealed holdout management, manager-facing employee analytics, distributed client recall, descendant quarantine, or a second bespoke promotion authority. These remain optional maturity work if scale, external distribution, offline clients, or autonomous merging later makes Git controls insufficient. A harmful revision can be disabled by pin/revert; high-risk capabilities may additionally use short cache TTLs or a denylist, without building a general distributed recall protocol.

## Governing boundary

```text
CASS/session collectors discover candidate evidence.
JSM and CM collect weak feedback and procedural hypotheses.
Deterministic systems and independently reviewed users establish outcomes.
An independent promotion authority decides what may become approved.
No component may evaluate, promote, or rewrite itself.
```

Native JSM success flags, CM helpful/harmful marks, prompt frequency, CASS rank, and LLM judgments are observations. None is promotion evidence by itself.

## Findings from the pre-build gauntlet

### Evidence is not ground truth merely because it is raw

Session histories contain assertions, hallucinations, partial work, injected tool content, unverified success claims, and repeated boilerplate. Every observation therefore carries a source type, authority, verification state, taint chain, privacy receipt, and deletion lineage. Repetition discovers hypotheses; it contributes no positive promotion weight without an independently verified outcome delta.

### Missingness can reverse the measured winner

For every experiment:

```text
assigned = success + failure + abstained + cancelled + timed_out
         + privacy_dropped + ingest_failed + missing
```

Unknown is never success. Promotion stops if coverage is unknown, exceeds a missingness bound, or differs materially by arm or critical slice. Evidence-plane health is independent from inference health: inference continues on the last approved revision, while promotion fails closed.

### Candidates cannot move their own goalposts

A behavioral candidate and its decisive evaluator cannot change in one promotion unit. Evaluator changes retain the prior production evaluator as a shadow oracle and require independent calibration and ownership. A meta-skill may not modify its own evaluator, permission set, evidence eligibility, approval policy, hard floors, or rollback threshold.

### Multiple model outputs are not necessarily independent

Model-family and evidence-method lineage are recorded. High-risk promotion requires a decisive non-generative executable oracle where possible and independent human/domain or distinct-family review. Three responses from one correlated model family do not constitute triangulation.

### Holdouts have an information budget

Development, promotion, and audit holdouts are separate. Promotion holdouts have access logs and query budgets. The audit set is available only to an independent release authority. Exhausted sets are retired rather than repeatedly mined by the proposal loop.

### Personal evidence does not become organizational knowledge by ACL implication

Permission to read, permission to analyze, and permission to generalize are distinct. Personal-to-team and team-to-organization promotion requires purpose-specific approval, rare-pattern/source-identifiability review, and provenance preservation. Manager access cannot nominate an individual's private corpus for organizational promotion.

### Aggregate dashboards can still surveil individuals

Minimum cohort size applies after every filter and export. Complementary cells and repeated-query differencing are suppressed. Personal analytics belong to the user. Skill metrics cannot be used for employment decisions. Security investigations use a separate, time-bounded purpose and authorization path.

### Rollback is recall, quarantine, and compensation—not an alias flip

Rollback changes the canonical alias, expires or re-attests cached high-risk clients, quarantines dependent revisions, and taints evidence produced by the recalled revision. External side effects require their own compensation. Deletion of influential evidence triggers dependency impact analysis and may require revalidation, restriction, or rollback.

## Canonical immutable records

### Skill identity and operational contract

Every revision is content-addressed and immutable. The contract includes:

- Stable skill ID, revision and parent revision
- Publisher, source revision, license, signatures and owners
- Personal, team or organization scope
- Lifecycle, skill class and risk tier
- Purpose, non-goals, positive and negative triggers, and abstention conditions
- Input/output schemas and permitted data classes
- Immutable child-skill, tool, rule-pack, model and knowledge dependencies
- Visibility, invocation, filesystem, network, secret and tool-parameter permissions
- Approval points and separation-of-duty policy
- Safety, privacy, policy-monotonicity and idempotency invariants
- Wall-time, call, token, cost, retry and concurrency budgets
- Timeout, dependency-failure, compensation, rollback and user-visible reason contracts
- Terminal, step and world-state validator revisions

Any content, dependency, permission, validator, evaluator, or contract change produces a new revision.

### Evaluation bundle

An evaluation bundle freezes:

- Candidate and baseline revisions
- Privacy-eligible evidence snapshot
- Inclusion probability, leakage groups, missingness policy and success/failure mixture
- Golden, conformance, metamorphic, fuzz, replay, adversarial and sealed holdout suites
- Task, difficulty, model, reasoning, tool, policy, environment, modality and risk slices
- Hard floors, non-regression margins and optimization metrics
- Evaluator, runner, sandbox, dependency-lock and region revisions

Case-level observations remain available to authorized auditors; aggregates include sample count, missing count, confidence interval, effect size and evaluator disagreement.

### Causal experiment

Every candidate experiment preregisters one causal claim, control and treatment digests, frozen cofactors, assignment unit, sticky hash version, exclusions, contamination controls, metrics, and stopping rule. Before/after comparisons are descriptive only. A bandit may choose among pre-approved safety-equivalent experiments, but its logged reward never authorizes publication.

### Promotion and rollback receipts

The signed receipt names the immutable candidate, transition, evidence bundles, hard-floor decisions, approvals, cohort assignment, observation window, rollback revision, triggers, kill switch and revalidation date. Exceptions cannot override critical privacy, authorization or security floors.

## Promotion ladder

### 0. Supply-chain admission

Validate manifest, schema, source, license, SBOM, digests, signatures, ownership, dependency closure, injection/malware scans, permissions and blast radius. Undeclared capabilities are a hard failure.

### 1. Golden contract

Positive, negative, abstain, failure and recovery cases pass executable terminal and world-state validators. A judge-only success is insufficient.

### 2. Conformance matrix

Run every declared model/tool dialect, environment, dependency boundary, timeout, cancellation, partial-result, retry and rollback contract. Unsupported combinations fail closed with stable reasons.

### 3. Metamorphic, fuzz and adversarial

Equivalent encodings, irrelevant ordering, renamed opaque IDs, duplicate events and runner/pod counts preserve invariants. Fixed-seed fuzzing proves no panic, hang, permission expansion, raw egress or budget escape. Adversarial suites cover stored prompt injection, poisoned evidence, confused deputy, stale dependency and approval bypass.

### 4. Offline replay and sealed holdout

Candidate and baseline use identical frozen cofactors. Hard privacy, policy, authorization and critical-slice floors pass before aggregate utility is considered. Report abstention, recovery, wrong and unnecessary tools, argument/order/result use, human edits, friction, latency, cost, transfer and negative transfer.

### 5. Shadow

The caller receives the baseline. Side effects are disabled, sandboxed, transactionally isolated or dry-run verified. Shadow has a separate bulkhead and budget. Privacy or policy divergence stops it automatically.

### 6. Sticky canary

Use approved bounded scope, session-sticky assignment, minimum and maximum exposure, preregistered stopping, an armed and tested kill switch, and a known rollback revision. Hard-floor violations automatically roll back.

### 7. Approved observation lease

Approval is scoped and expires. Continue baseline sampling and drift monitoring across task/model/tool/policy/environment slices. Dependency or permission changes trigger blast-radius-based quarantine or revalidation. A canary pass is not permanent proof.

## Auto-promotion boundary

At launch, no organization-scoped JSM skill auto-promotes. Automation may prepare evidence, tests, patches, issues, and draft merge requests. Publication occurs only through protected Git merge by an authorized human; the gateway has no merge or branch-protection-bypass authority.

These classes never auto-promote:

- Governance/meta skills, evaluators, routers, policies and evidence rules
- Identity, authorization, credentials, secrets, keys, audit, retention, deletion, privacy, residency and compliance
- Permission/capability expansion or dependency changes
- Mutating or privileged shell, filesystem, database, cloud, Kubernetes, deployment, browser or computer operations
- Destructive, financial, procurement, external communication, legal, HR, health or account administration
- Personal-to-team, team-to-organization or cross-tenant transfer
- Employee-related analytics
- Evaluator changes judging the same candidate

A possible future exception is an explicitly opted-in personal-scope formatting or clarification change with no side effects, permissions, dependency changes or authoritative factual claims, after long clean evidence and bounded canary. A bandit selects tests, never approval.

## Core promotion invariants

1. Self-reports and weak feedback can create gap cases but cannot satisfy a promotion floor.
2. Every assigned experimental unit reaches a terminal disposition or explicit missingness record.
3. Evidence loss, privacy dropping and ingestion failures remain in denominators.
4. Frequency is discovery evidence only.
5. Candidate authors and executing agents cannot supply the decisive vote.
6. Candidate behavior and decisive evaluator cannot change together.
7. Holdouts are separated, access-logged and query-budgeted.
8. At least one decisive oracle is methodologically independent.
9. Hard security/privacy/authorization failures cannot be averaged against utility.
10. Safe abstention and escalation are not automatically failures.
11. Permission expansion is a separate security decision, never a quality promotion.
12. Promotion fails closed on unknown evidence health; inference continues.
13. Deletion triggers influence and dependency review.
14. Rollback includes distributed recall, descendant quarantine and evidence taint.
15. High-risk organization promotion separates proposer, evaluator owner, approver and rollout authority.

## Tooling preflight result

The installed NTM core, Beads, CM, DCG and JSM binaries are present. The preflight found degraded Agent Mail and CASS health, uninitialized repo CM state, NTM privacy/encryption defaults disabled, and UBS unable to run under macOS Bash 3.2. These are tooling reliability findings, not permission blockers. They remain prerequisites before an implementation swarm is treated as auditable or complete.

## Reality check: current implementation status

As of 2026-07-15, the managed Flywheel is **not implemented**. Repository search finds no production Go definitions for `AgentEvidenceEnvelope`, `SkillOperationalContract`, `SkillPromotionReceipt`, `EvidenceEnvelopeBuilder`, or `EvidenceOutbox`. No mock-free Flywheel E2E exists, and no promotion or rollback workflow is runnable.

What is real today:

- The underlying Bifrost request, plugin, trace, governance, MCP, log/config store and test infrastructure.
- Repository-grounded architecture, privacy, reliability, security and evaluation contracts.
- A Beads graph covering the initial evidence plane, promotion authority, conformance, fuzzing, distributed recall and failure campaigns.
- Existing reusable testing patterns for schemas, backend parity, MCP fixtures, provider goldens and Playwright/API E2E.

What remains aspirational:

- All managed evidence ingestion, storage, indexing and deletion behavior.
- All skill registry, evaluation, causal experiment, shadow, canary, promotion and recall behavior.
- Cross-language endpoint collectors and canonical parsing.
- Evidence-plane security isolation, privacy transforms and resource controls.
- Every claimed multi-pod, Aurora, offline-client and production-degradation proof.

Current graph health reports 197 open issues, zero closed issues, 42 actionable issues and no dependency cycles. This is a plan-space program, not a nearly completed product. The next correct implementation entry points remain the enterprise seam matrix, `PrivacyTransformReceipt`, `AgentEvidenceEnvelope`, and mandatory request-guard contract. Starting downstream Flywheel code before those contracts would create incompatible schemas and unsafe enforcement semantics.
