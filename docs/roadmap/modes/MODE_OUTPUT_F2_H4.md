# F2 Dependency Mapping + H4 Mechanism Design

Scope: launch-critical virtual keys, budgets/controlled overdraft, Okta-derived
entitlements, cross-pod state, routing, MCP governance, and trace-to-draft-MR skill
improvement. Deployment is internal Kubernetes with Aurora PostgreSQL. Human review
and protected Git merge are the **only** authority that can promote a skill revision.

## Executive finding

The plan has the right components but several Beads encode implementation order as if
downstream products defined their own authority. The launch needs four explicit seams:

1. **Policy authoring** produces versioned desired state; it does not grant access.
2. **Aurora transactions** commit desired state plus a durable outbox event; `NOTIFY`
   is only a wakeup. Pods enforce immutable local snapshots with bounded freshness.
3. **Request admission** reserves quota and fixes the eligible candidate set before
   adaptive routing ranks anything. Routing cannot restore a denied candidate.
4. **Flywheel automation** may propose a Git diff. Protected-branch CI and a human MR
   approval are the sole skill-promotion transition.

Without those seams, the graph encourages circular implementations: key APIs before
distribution, Okta import after SCIM despite being a separate mechanism, routing before
its authoritative snapshot contract, and skill proposal automation without its actual
trace/proposal input.

## Actual coupling found in code

### Virtual keys, models, and budgets are one request-admission mechanism

`BudgetResolver.EvaluateVirtualKeyRequest` resolves active/expiry state, then provider
and model eligibility, then rate-limit and budget hierarchies, and finally provider-key
filtering (`plugins/governance/resolver.go:245-359`). Empty provider configurations deny
all providers and models (`resolver.go:365-412`). This means Okta group mapping cannot be
implemented as a UI-only team association: its compiled result must populate the same
virtual-key/provider/model snapshot consumed here.

The budget check is described as atomic (`resolver.go:442-453`), but the current launch
store is local memory. Configuration replacement deliberately preserves pod-local
`CurrentUsage` and reset state via compare-and-swap (`plugins/governance/store.go:280-314`,
`347-376`), and DB baselines are explicitly described as inputs to gossip deltas
(`store.go:317-334`, `379-402`). This is process-safe, not fleet-atomic. Consequently:

- cross-pod invalidation is sufficient for key/entitlement **configuration**;
- hard budget admission requires a separate Aurora reservation/ledger operation;
- copying `CurrentUsage` through the config outbox would create lost updates or double
  counting and must be prohibited.

Post-hook accounting occurs after provider execution and streaming completion paths
(`plugins/governance/main.go:1312-1365`), so it cannot be the hard-limit authority.
Reservation, renewal for long streams, actual-use reconciliation, abandonment expiry,
and retry/fallback charging are prerequisites for controlled overdraft.

### Routing already mixes authorization and optimization

The governance pre-route path applies rules, load balancing, and MCP grant narrowing
(`plugins/governance/main.go:412-449`). Load balancing filters by model, budget, and rate
limit before weighted selection (`main.go:469-547`). This is useful behavior but a hidden
coupling: adaptive health, canaries, and learned routing will be unsafe if they become a
second candidate generator. The versioned route DAG must consume an immutable
`EligibleCandidateSet` plus policy revision, never raw provider inventory.

The selected architecture already says hard filters precede learned scoring
(`docs/roadmap/technical-decision-options.md:314-324`). Beads should make that a type and
dependency boundary, not merely an acceptance statement.

### MCP filtering and credential acquisition remain separate authority surfaces

Virtual-key MCP grants are narrowed in governance, with explicit per-key configuration
overriding `AllowOnAllVirtualKeys` (`plugins/governance/main.go:801-885`, `1142-1181`).
However, direct connection construction can still obtain credential headers when a
caller does not provide pre-approved overrides (`core/mcp/clientmanager.go:1660-1679`).
Therefore policy-before-search alone is insufficient: policy and immutable tool revision
must be checked before credential resolution, connection acquisition, and every call.
`bif-bpfk.19` is a real launch security dependency and should not be deferred merely
because skill publication uses human MR review.

### The Git MR boundary is simpler than the existing Flywheel graph

The launch contract correctly prohibits merge credentials and direct publication and
pins execution to commit SHA (`docs/roadmap/jsm-flywheel-gauntlet-and-promotion-contract.md:5-18`,
`151-166`). Human approval reduces autonomous-promotion risk, but it does not protect
private trace material in a proposed diff or prevent candidate tests from exfiltrating
CI credentials. Privacy-gated evidence construction and credentialless sandboxed CI
remain prerequisites. Causal holdouts, bandit promotion, distributed recall, and a
second promotion state machine are not launch dependencies.

## Authority and incentive design

| Decision | Sole authority | Automation may do | Automation must not do |
|---|---|---|---|
| Key/entitlement mutation | Aurora transaction with actor/policy revision | Validate, preview, write outbox in same transaction | Mutate only a pod cache |
| Request authorization | Fresh immutable local policy snapshot | Explain denial and record revision | Query Okta or widen stale policy |
| Hard budget admission | Aurora fenced reservation ledger | Estimate, reserve, renew, reconcile, alert | Treat post-hook/local counter as fleet truth |
| Overdraft | Preconfigured rule or authorized approval receipt | Alert, request approval, enforce bounded amount/time | Infer approval from successful spend |
| Route choice | Ordered policy pipeline | Rank only eligible candidates | Reintroduce entitlement-denied targets |
| MCP invocation | Policy check bound to tool digest and arguments | Discover after filtering; acquire attenuated credential | Acquire credentials before authorization |
| Skill promotion | Protected Git merge plus required human approval | Mine traces, open issue/draft MR, run sandboxed CI | Merge, publish, bypass checks, attach raw traces |

Incentives should be measured against these authorities. Operators need alerts before
and during overdraft, approvers need a bounded amount/window and spend projection, and
route optimizers must be rewarded only after hard-policy and reserved-budget decisions.
Skill proposal quality metrics must never reward MR volume or acceptance rate alone;
those invite noisy or privacy-invasive proposals. Prefer verified defect reduction,
review effort, rollback rate, and downstream deterministic-test improvement.

## Precise recommended Beads graph edits (do not apply automatically)

### Incorrect or inverted edges

1. **Remove `bif-kyy.5.3 -> bif-kyy.5.2`.** The Okta directory importer is explicitly
   separate from inbound SCIM. Both should depend on the canonical identity schema and
   reconciliation contract (`bif-kyy.2.1` plus a new identity-link task). Sharing SCIM
   resource types is fine; requiring a deployed SCIM server is not.
2. **Remove `bif-kyy.5.4 -> bif-kyy.3.2`.** Entitlement compilation must exist before
   managed key issuance can materialize grants. Split `bif-kyy.3.2` into generic key
   lifecycle APIs and managed issuance; make only managed issuance depend on `5.4`.
3. **Remove `bif-kyy.6.1 -> bif-kyy.3.2` and `bif-kyy.6.1 -> bif-kyy.4.1`.** Cluster
   propagation/runtime is substrate, not a consumer of finished key and quota products.
   Make key mutation emission depend on the outbox contract; make quota reservation
   depend on its Aurora authority contract. Keep `6.1 -> 6.4/6.5/6.6`.
4. **Remove `bif-kyy.4.6 -> bif-kyy.5.4`.** Controlled overdraft needs a principal and
   authorization/approval contract, not full Okta group-to-model mapping. Depend on
   `bif-kyy.2.2` and the budget algebra/receipt task `bif-kyy.4.7`; optionally consume
   group approver roles later.
5. **Split `bif-kyy.7.1`.** A policy-pipeline contract should depend on schemas
   (`2.2`, `2.4`, `7.7`, `7.8`) but not the completed quota implementation `4.1`.
   A separate admission adapter should depend on both the contract and `4.1`. Otherwise
   routing design is blocked by an implementation it must structurally constrain.
6. **Remove `bif-kyy.7.3 -> bif-kyy.7.2` for basic deterministic canary assignment.**
   Canary bucketing and rollback do not require adaptive circuits. Split deterministic
   rollout from health-adaptive routing; shadows additionally depend on `4.2` and secure
   replay.

### Missing prerequisites

7. Add **Canonical principal/linking and entitlement compiler contract** before `5.2`,
   `5.3`, and `5.4`: immutable Okta/OIDC/SCIM IDs, rename/rehire/merge semantics, deny
   precedence, provenance, generation/tombstones, and explain-access output.
8. Add **Transactional governance mutation + outbox writer** after `6.4/6.8`; make
   `3.2`, `5.4`, MCP grant mutations, routing-policy mutations, and revocation tests use
   it. `NOTIFY` remains an optional wakeup; cursor catch-up is the proof of convergence
   (`technical-decision-options.md:79-100`, `187-198`).
9. Add **Immutable snapshot compiler and freshness gate** before `3.3`, `5.4`, `7.1`,
   and `15.5`: monotonic tenant revision, atomic swap, cold-start readiness, stale-policy
   semantics, resnapshot and poison-event handling.
10. Add **Fenced budget reservation API and ledger invariant** before `4.1`; make `4.2`,
    `4.6`, `4.9`, routing admission, and multi-pod tests depend on it. Explicitly state
    that config propagation never carries mutable usage authority.
11. Add **EligibleCandidateSet/DecisionReceipt type** before `7.1`, `7.2`, `7.3`, and
    `7.10`, containing policy and pricing revisions, denial reasons, reservation ID, and
    only authorized targets. Require monotonic subset properties across retries/fallbacks.
12. Make `bif-kyy.15.5` depend on the immutable snapshot/freshness task and make
    `bif-kyy.15.2`, `15.4`, and all tool execution paths depend on `bif-bpfk.19` or its
    extracted policy-before-credential contract.
13. Add `bif-bpfk.7 -> bif-kyy.15.9` because the Git/MR workflow consumes a
    `SkillChangeProposal`; add `bif-bpfk.7 -> bif-kyy.13.1` (or `8.1` plus explicit
    privacy eligibility) when the proposal uses traces. Keep `bpfk.7 -> bpfk.18` for
    bounded, redacted evidence export.
14. **Do not add `bif-bpfk.7 -> bif-bpfk.14/.15/.16/.17/.21/.22/.23/.25/.26`.** Those
    are maturity controls for autonomous/large-scale promotion, recall, surveillance
    analytics, and exhaustive testing. Human MR authority intentionally removes them
    from launch critical path.
15. Reframe `bif-kyy.15.10` as **pre-merge validation and post-merge SHA pin/revert**, or
    split it. It must not imply that gateway canary metrics promote skill revisions.
    The only promotion edge terminates at protected human merge; runtime rollout begins
    from an already merged immutable SHA.

## Minimal launch dependency spine

```text
canonical schema + authority contract
  -> principal/linking + entitlement compiler
  -> transactional mutation + outbox
  -> cursor consumer + immutable snapshot + freshness gate
  -> key/model/MCP admission

budget algebra
  -> fenced Aurora reservation ledger
  -> request admission + renew/reconcile
  -> controlled overdraft receipt + alerts

admission decision / EligibleCandidateSet
  -> deterministic routing and fallback
  -> circuits / canary / shadow (independent optional layers)

privacy-eligible trace envelope
  -> SkillGapCase / SkillChangeProposal
  -> redacted patch + credentialless CI
  -> draft MR
  -> protected human merge (sole promotion authority)
  -> immutable SHA rollout and revert
```

## Release-blocking proofs

- A revoked key and removed group entitlement deny on every pod within the stated
  one-to-five-second bound, including notification loss and listener reconnect.
- No pod becomes ready with an unverified or rollbacked snapshot.
- Concurrent requests cannot exceed hard allowance except through a bounded, auditable
  overdraft receipt; retries, streams, crashes, and reservation expiry conserve usage.
- Every fallback/canary/learned route is a subset of the admitted candidate set.
- MCP discovery, credential resolution, and execution cannot occur before policy bound
  to the exact tool digest and arguments.
- Trace-derived draft MRs contain no raw private payload, CI has no production secrets,
  the gateway lacks merge authority, and rollback to a prior commit SHA is rehearsed.
