# JSM Flywheel Evaluation Conformance Specification

Status: normative pre-implementation test contract

## Launch conformance profile

For the internal Git marketplace, this document's full matrix is a maturity target rather than a launch gate. Launch conformance is limited to the controls that human merge-request review cannot replace:

1. Skill manifests and permission/dependency diffs are canonical, schema-valid, and tied to an immutable commit SHA.
2. Synthetic secret/PII canaries prove denied data cannot enter evidence, generated patches, CI artifacts, issues, or merge requests.
3. Candidate validation runs in a sandbox with no inherited production credentials and explicit filesystem/network/tool capabilities.
4. Branch protection, required CI, CODEOWNERS or equivalent ownership, and human approval cannot be bypassed by the gateway or proposal worker.
5. A focused deterministic suite and capability-relevant real-service smoke test pass before merge.
6. Runtime selection is pinned to a revision, and a revert or last-known-good pin is tested as the rollback path.

The causal experiment ledger, sealed holdouts, evaluator-independence machinery, organization analytics red team, distributed recall, descendant quarantine, exhaustive mutation/metamorphic suites, and broad failure campaigns are deferred until the product introduces autonomous merging, external publishers, offline distribution, or evidence-based production selection. Parsers, authorization boundaries, privacy transforms, and other security-sensitive input surfaces may still require fuzzing where their local threat model warrants it.

## Oracle hierarchy

The Flywheel must choose the strongest available oracle for each claim:

1. **Exact executable assertion** when the expected state is computable.
2. **Differential conformance** when a pinned reference implementation exists.
3. **Reviewed golden artifact** for complex deterministic output.
4. **Metamorphic relation** when exact output is unknowable but transformations have invariant effects.
5. **Independent human or calibrated judge evidence** only when stronger oracles are unavailable.

Lower-strength evidence cannot override a higher-strength contradiction. An LLM judgment cannot turn a failed deterministic validator into success.

## Normative conformance matrix

Each requirement receives a stable ID, level, executable test, provenance, and verdict. `SKIP` is forbidden for known divergences; use an explicit expected failure with owner and review date.

| ID | Level | Requirement | Primary oracle |
|---|---|---|---|
| EV-MUST-001 | MUST | Every assigned experimental unit reconciles to a terminal disposition or explicit missingness | Exact ledger invariant |
| EV-MUST-002 | MUST | Unknown, privacy-dropped, cancelled and ingest-failed outcomes are never counted as success | Table-driven conformance |
| EV-MUST-003 | MUST | Native JSM/CM/CASS feedback cannot satisfy a promotion floor | Negative authorization test |
| EV-MUST-004 | MUST | Candidate and decisive evaluator cannot change in one promotion unit | Registry state-machine test |
| EV-MUST-005 | MUST | A meta-skill cannot alter its own evaluator, permissions, approval policy or rollback threshold | Adversarial conformance |
| EV-MUST-006 | MUST | Critical privacy, authorization and security failures block promotion regardless of aggregate utility | Exact promotion-policy test |
| EV-MUST-007 | MUST | Promotion fails closed when authoritative evidence health or arm coverage is unknown | Fault-injection test |
| EV-MUST-008 | MUST | Inference continues on the last approved revision when the evidence plane fails | Real-service E2E |
| EV-MUST-009 | MUST | Evidence envelopes contain no denied headers, credentials or unapproved raw content | Generated secret-canary test |
| EV-MUST-010 | MUST | Privacy and deletion lineage covers summaries, embeddings, proposals, fixtures and promoted dependencies | Graph conformance |
| EV-MUST-011 | MUST | Personal evidence cannot widen scope without purpose-specific promotion authorization | Tenant/scope isolation test |
| EV-MUST-012 | MUST | Organization analytics resist small cohorts, complementary cells and repeated-query differencing | Query red-team harness |
| EV-MUST-013 | MUST | Promotion receipts bind immutable skill, evaluator, runner, policy, tool, model and evidence revisions | Round-trip/schema test |
| EV-MUST-014 | MUST | Rollback changes canonical assignment, recalls expiring clients, quarantines descendants and taints produced evidence | Multi-client E2E |
| EV-MUST-015 | MUST | Permission or capability expansion requires a separate security approval | Policy state-machine test |
| EV-MUST-016 | MUST | Shadow execution has no production side effect and cannot delay inference | World-state plus latency test |
| EV-MUST-017 | MUST | Canary assignment is deterministic and sticky at the declared unit | Property/conformance test |
| EV-MUST-018 | MUST | Evidence queue saturation obeys explicit metadata-only/drop/reject policy without unbounded memory | Soak and fault injection |
| EV-MUST-019 | MUST | MCP policy runs before credential issuance and connection acquisition | Instrumented sequence test |
| EV-MUST-020 | MUST | Pooled objects cannot retain tenant, evidence, policy, skill or privacy fields | Reflective reset/fuzz test |
| EV-SHOULD-001 | SHOULD | Replay reports exact, transformed, substituted and non-reproducible components | Structural golden |
| EV-SHOULD-002 | SHOULD | Scorecards report task/model/tool/policy/environment/risk slices with n, missingness, interval and effect | Canonical JSON golden |
| EV-SHOULD-003 | SHOULD | Safe abstention and escalation are reported independently from failure | Table-driven conformance |
| EV-SHOULD-004 | SHOULD | Holdout query budget and exhaustion are visible in the promotion receipt | State-machine test |
| EV-SHOULD-005 | SHOULD | Evidence-method and model-family lineage reveal correlated evaluators | Graph/structural golden |

MUST coverage target is 100%. A release with any untested MUST is non-conformant. Intentional divergences require `DISCREPANCIES.md`, an `XFAIL`, owner, rationale, affected tests and review date.

## Harness layout

```text
tests/flywheel/
  SPEC.md
  COVERAGE.md
  DISCREPANCIES.md
  fixtures/
    PROVENANCE.md
    evidence_envelopes/
    skill_contracts/
    promotion_receipts/
    replay_episodes/
    adversarial_sessions/
  golden/
    envelopes/
    scorecards/
    receipts/
    dependency_graphs/
  conformance/
  metamorphic/
  fuzz/
  e2e/
  reports/compliance.json
  reports/compliance.md
```

Each fixture records generator command, source revision, dependency lock, privacy classification, review identity and creation time. Fixture content is synthetic or explicitly privacy-eligible.

## Golden confidence matrix

| Artifact | Deterministic | Volatility | Strategy | Required review |
|---|---:|---:|---|---|
| SkillOperationalContract canonical JSON | Yes | 1 | Exact canonicalized | Contract owner |
| Promotion/rollback receipt canonical JSON | Yes | 2 | Exact with timestamp/ID scrub | Governance owner |
| Evidence envelope | Yes | 3 | Scrubbed semantic | Privacy owner |
| Permission/dependency diff | Yes | 2 | Structural plus exact stable fields | Security owner |
| Compliance report | Yes | 2 | Canonicalized exact | Test owner |
| Evaluation scorecard | Partly | 4 | Structural plus frozen numeric tolerances | Evaluation owner |
| Replay explanation | Partly | 5 | Structural; never exact prose | Domain reviewer |
| Model-generated output | No | 5 | Do not golden raw prose; validate schema/world state/metamorphic relation | Domain reviewer |

Goldens are never automatically updated in CI. Update mode produces `.actual` artifacts, a unified diff and a required approval. Goldens larger than 100 KB are decomposed into reviewable focused files.

## Metamorphic strength matrix

Score is fault sensitivity times independence divided by relative cost. Only relations scoring at least 2.0 are implemented, and every implemented relation must kill at least one planted mutation.

| ID | Transformation and required relation | Category | Sensitivity | Independence | Cost | Score |
|---|---|---|---:|---:|---:|---:|
| MR-01 | Rename opaque tenant/user/session/task IDs consistently; promotion verdict and metrics remain unchanged | Equivalence | 5 | 5 | 2 | 12.5 |
| MR-02 | Reorder evidence events with the same causal sequence/revisions; terminal ledger and verdict remain unchanged | Permutative | 5 | 4 | 2 | 10.0 |
| MR-03 | Duplicate an event with the same idempotency key; counts and verdict remain unchanged | Equivalence | 5 | 5 | 1 | 25.0 |
| MR-04 | Add irrelevant sanitized metadata; permissions, outcome and promotion verdict remain unchanged | Equivalence | 4 | 4 | 2 | 8.0 |
| MR-05 | Remove or privacy-drop observations; sample and missing counts change predictably and verdict cannot improve solely from loss | Inclusive | 5 | 5 | 2 | 12.5 |
| MR-06 | Narrow candidate permissions; admission cannot become less safe, though capability conformance may become unsupported | Inclusive | 5 | 4 | 2 | 10.0 |
| MR-07 | Expand candidate permissions; quality evidence remains unchanged but separate security approval becomes mandatory | Inclusive | 5 | 5 | 2 | 12.5 |
| MR-08 | Add one critical policy violation to an otherwise successful cohort; promotion must fail | Additive/hard-floor | 5 | 5 | 1 | 25.0 |
| MR-09 | Swap proposer and approver identities to the same subject; promotion changes from eligible to denied | Invertive/authorization | 5 | 4 | 1 | 20.0 |
| MR-10 | Change model revision while skill stays fixed; result must be sliced or invalidated, never attributed solely to the skill | Covariant | 5 | 5 | 3 | 8.3 |
| MR-11 | Change evaluator revision while candidate stays fixed; existing evidence becomes incomparable until re-evaluation | Covariant | 5 | 5 | 2 | 12.5 |
| MR-12 | Increase pod/worker count with the same event set; authoritative ledger and promotion verdict remain identical | Equivalence | 5 | 4 | 3 | 6.7 |
| MR-13 | Delete influential evidence; dependent revision moves monotonically toward revalidation/restriction, never stronger approval | Inclusive | 5 | 5 | 3 | 8.3 |
| MR-14 | Roll back a parent skill; every reachable dependent is quarantined regardless of graph traversal order | Graph equivalence | 5 | 5 | 3 | 8.3 |
| MR-15 | Paraphrase non-authoritative narrative while preserving executable artifacts; deterministic verdict remains unchanged | Equivalence | 4 | 4 | 3 | 5.3 |

Compound relations include rename + reorder + duplicate, and privacy-drop + pod-count change + replay. The suite target is at least 80% kill rate over a documented mutation set.

## Required planted mutations

- Treat unknown as success.
- Drop failures before aggregation.
- Deduplicate by payload instead of event ID.
- Allow candidate author to approve.
- Permit candidate/evaluator joint revision.
- Average critical privacy failure against utility.
- Reuse exhausted holdout without recording access.
- Ignore transitive dependencies during rollback.
- Fail to propagate a deletion tombstone.
- Capture Authorization, Cookie, virtual-key or tool credential fields.
- Run evidence export synchronously on inference.
- Acquire MCP credentials before policy approval.
- Leave a sensitive pooled field uncleared.

Every surviving mutant is classified as equivalent, unreachable, or a coverage gap. Unsupported claims cannot be hidden as skipped tests.

## Existing Bifrost patterns to reuse

- Table-driven Go tests and Testify assertions in core/framework/plugins.
- Config schema conformance tests in `transports/schema_test`.
- Provider payload ordering goldens.
- Three-backend log-store parity testing.
- MCP scenario fixtures and agent tests.
- Playwright feature tests and Postman/Newman API collections.
- Go native fuzz tests for parsers, event order, state machines and pooled reset behavior.

These patterns should be extended with stable requirement IDs and generated compliance accounting rather than replaced with a separate test framework.

## Fuzzing campaign

Fuzz the narrow deterministic boundary, not the entire gateway. Structured inputs use structure-aware generation and the strongest available invariant; crash-only oracles are insufficient where a state model or round trip exists.

| Target | Archetype | Oracle | Minimum corpus |
|---|---|---|---|
| AgentEvidenceEnvelope parser/canonicalizer | Structure-aware plus round trip | Decode-encode identity and schema invariants | empty, minimal, full, unknown fields, maximum sizes, hostile strings |
| SkillOperationalContract and permission manifest | Grammar/structure-aware | Admission-policy state model | valid classes, missing owners, mutable refs, capability expansion, self-approval |
| Evaluation ledger reducer | Stateful | Simple authoritative shadow ledger | every disposition, duplicates, reordered events, partial batches, conflicting terminal states |
| Promotion state machine | Stateful | Explicit lifecycle transition model | every stage, rollback, quarantine, expiry, exception and denial |
| Dependency/recall graph | Stateful graph | Reachability and monotonic quarantine invariants | cycles, diamonds, deep chains, missing nodes, mixed revisions |
| Privacy envelope builder | Structure-aware/differential | Denylist, allowlist and privacy receipt invariants | credential canaries in every nested field and encoding |
| Evidence outbox recovery | Stateful/concurrency | No-loss/no-duplicate contract according to configured policy | crash points, disk-full, poison event, stale lease, concurrent consumers |
| MCP normalized invocation manifest | Structure-aware | Policy-before-credential sequence invariant | alias collision, stale tool, hostile schema, injected result, ambiguous completion |
| Pooled reset lifecycle | Stateful/concurrency | Reflective semantic-zero oracle | every sensitive field populated, randomized release/reacquire sequence |
| Canary assignment | Property/stateful | Determinism, stickiness and cohort-bound invariants | tenant/user/session/task IDs, weight boundaries and revision changes |

Go-native fuzz targets must enforce input-size bounds, deterministic seeds, no external I/O, a minimized seed corpus, and permanent regression tests for every crash or invariant violation. Parser targets should sustain at least 1,000 executions/second and stateful targets at least 100; slower harnesses must be repaired before extended campaigns. Concurrent targets run race-enabled campaigns separately. Corpora are minimized regularly and failures are deduplicated by root cause, not artifact filename.

Required fault campaigns include duplicate and reordered delivery, conflicting terminal outcomes, integer/count overflow, malformed Unicode, deeply nested JSON, decompression/expansion bombs where applicable, dependency cycles, authorization confusion, privacy-encoded credentials, queue saturation, process death at every durability boundary, and concurrent rollback/promotion/deletion.

## Mock-risk and real-service E2E matrix

Critical distributed claims cannot be proven with in-memory mocks. Tests use real PostgreSQL-compatible behavior, real gateway processes, real network connections and multiple pods/processes. Provider calls may use explicitly scoped test endpoints where billing or nondeterminism would prevent a stable oracle; the gateway/database/control-plane behavior itself is not mocked.

| Flow | Impact | Mock divergence | Score | Requirement |
|---|---:|---:|---:|---|
| Aurora outbox commit, polling, resnapshot and compaction | 5 | 5 | 25 | Real PostgreSQL/Aurora-compatible E2E |
| Evidence deletion and tombstone propagation | 5 | 5 | 25 | Real DB, object/index adapters and restart |
| Promotion, canary, rollback and descendant quarantine | 5 | 5 | 25 | Real DB plus multiple gateway/worker processes |
| Principal/tenant isolation | 5 | 5 | 25 | Real auth/session/API and DB constraints |
| Evidence saturation while inference continues | 5 | 5 | 25 | Real bounded spool, disk/DB fault and gateway load |
| MCP policy before credential/connection | 5 | 4 | 20 | Real MCP server and instrumented credential broker |
| Mixed-version migration and rollback | 5 | 5 | 25 | N/N+1 binaries and real schema migration job |
| Skill client recall after offline interval | 4 | 5 | 20 | Multiple real clients with cache/expiry behavior |
| Analytics cohort/differencing protections | 5 | 4 | 20 | Real query API and DB with adversarial query sequence |
| Canonical JSON formatting helper | 1 | 1 | 1 | Pure unit test acceptable |

The E2E harness must:

1. Block every configured production database, provider, Kubernetes, identity and object-store endpoint.
2. Provision isolated namespaces/databases and realistic factories for tenants, principals, skills, dependencies, evidence and experiments.
3. Use transactions where a single connection suffices; use unique run IDs plus a LIFO cleanup registry for cross-process tests.
4. Emit structured JSONL phases, timings, revision IDs, process/pod identities, database snapshots/counts and assertion outcomes without sensitive content.
5. Exercise pod/process death, restart, network partition, delayed delivery and mixed revisions at deterministic checkpoints.
6. Assert external world state and durable database state, not merely HTTP success.
7. Retain minimized failing scenarios and promote every production incident into a mock-free regression.
8. Prove the gateway's inference SLO independently while evidence workers, indexes and evaluators are stopped or corrupt.

## Initial mock-free scenarios

1. **Inference survives evidence outage:** stop all evidence consumers and fill the bounded spool to each configured threshold; verify the documented metadata-only/drop/reject outcome and stable inference latency.
2. **Promotion stops on differential loss:** drop candidate-arm events while preserving baseline events; verify inference continues but promotion becomes ineligible.
3. **Three-process convergence:** create, revoke and rotate a skill/permission revision while cycling processes; all live consumers converge within the declared SLO and stale high-risk clients expire.
4. **Deletion invalidates evidence:** delete an influential source; tombstone every mirror/index, recalculate coverage, and move the dependent revision to the correct restricted state.
5. **Rollback recalls descendants:** promote a parent and child, take one client offline, recall the parent, reconnect the client, and prove canonical alias rollback, descendant quarantine and evidence taint.
6. **MCP authorization ordering:** attempt a denied tool invocation and assert no credential issuance, connection acquisition or upstream wire call occurred while a denial receipt was durably emitted.
7. **Privacy canary:** place synthetic credentials and PII in every trace/header/plugin/MCP/error surface; verify no denied value enters envelope, outbox, index, evaluator or golden artifact.
8. **Evaluator separation:** propose a behavior change plus a weaker evaluator; verify the registry splits or rejects the promotion and retains the prior oracle.
9. **Analytics differencing:** issue overlapping team/repository/time/model filters designed to isolate one user; verify complementary suppression and query-budget enforcement.
10. **Mixed-version durability:** run N and N+1 producers/consumers across migration, rollback and poison-event recovery; prove schema and event compatibility or explicit refusal.
