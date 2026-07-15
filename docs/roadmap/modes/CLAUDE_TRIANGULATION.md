# CLAUDE Triangulation — Dissenting Architecture Review

Date: 2026-07-15
Reviewer role: dissenting architecture reviewer (adversarial, independent).
Inputs triangulated: the ten `MODE_OUTPUT_NTM_*.md` mode files (A1, B5, F2, F4, F7, H4, I4, L1, L3, L5), `multimodal-voice-image-provider-audit.md`, the live Beads graph (`br`), and direct read-only inspection of the repository at the current tree state.
Method: I did not treat the mode files as ground truth. I re-derived their load-bearing claims from code and the Beads graph, and I only certify a claim as consensus after it survived my own inspection. Two widely-repeated claims did **not** survive as stated and are corrected below. Line numbers are for the current tree and may drift.

---

## 1. Consensus kernel (survives independent verification)

All ten mode files converge on the same launch architecture, and every load-bearing element below was confirmed against code. This is the part of the analysis I endorse without reservation.

**K1 — Keep the Go data plane; add a small Aurora-authoritative control plane.** No mode file recommends a rewrite. The provider/plugin/queue substrate stays hot; enterprise authority moves into immutable per-pod snapshots plus a mandatory pre-provider decision. *Verified:* atomic provider/plugin pointers and per-provider queues are real (`core/bifrost.go`), and the governance store is genuinely process-local `sync.Map` state (`plugins/governance/store.go:24-66`).

**K2 — Mandatory controls cannot inherit best-effort plugin error semantics.** This is the single most-repeated finding (A1-F2, B5-F01, F2-01, F4-03, F7-01, H4-08, I4-03, L1-01, L3-01, L5-F01). *Verified:* `core/schemas/plugin.go:192-204,283-294` documents plugin errors as non-blocking; `core/bifrost.go:7300-7338` logs `PreRequestHook` errors and continues; the only hard-deny path today is a `PreLLMHook` short-circuit (`plugins/governance/main.go:1271-1310`). The critique is correct. Bead `bif-kyy.2.4` tracks it and correctly fans out as a blocker to MCP firewall (`bif-kyy.15.3`), sanitized-copy sinks (`bif-kyy.16.5`), routing (`bif-kyy.7.1`), and the three-pod slice (`bif-kyy.14.3`).

**K3 — Budgets need admission-time reservations, not post-hoc settlement.** *Verified:* usage is applied asynchronously from `PostLLMHook` (`plugins/governance/main.go` `PostLLMHook`), there is no pre-provider reserve/commit path, and `TableBudget` has no reservation/overdraft/lease/settlement fields (`framework/configstore/tables/budget.go`). Bead `bif-kyy.4.9` (fenced renewable reservations, attempt epochs, CAS settlement) is the correct spine. **Caveat: the mechanism the mode files cite as evidence is mis-described — see §2, D1.**

**K4 — Aurora outbox/snapshot/NOTIFY convergence is specified but not implemented.** *Verified independently:* `grep` for `pg_notify`, `LISTEN/NOTIFY`, and `transactional outbox` across `core framework transports plugins` returns **zero** `.go` matches. The convergence contract exists only in the roadmap. Beads `bif-kyy.6.7` (stale-policy classes) and `bif-kyy.6.8` (outbox cursor lifecycle, poison recovery, WAL/autovacuum oracles) are the right shape.

**K5 — MCP mandatory policy runs after connection acquisition.** *Verified:* `core/mcp/exec.go:82-124` acquires the client connection in `prepareToolExecution` *before* `RunWithPluginPipeline`, whose op closure wraps only the wire `CallTool`. `ConnectionHeaders` returns admin-level headers under a synthetic no-identity context for shared-connection auth types (`core/schemas/mcp.go:126-143`), which is the credential-side-effect the reviewers worry about. Bead `bif-bpfk.19` states the exact target order and the zero-credential/zero-connection/zero-packet acceptance test. **Caveat: the "Starlark is the clearest pressure point" sub-claim is now stale — see §2, D2.**

**K6 — Privacy: one pre-sink transform receipt, not per-sink content toggles.** *Verified:* content logging defaults on (`plugins/logging/main.go`), raw request/response and passthrough bodies are captured when gated flags allow, and traces snapshot for export race-safety without privacy transformation. No unified `PrivacyTransformReceipt` exists in code. Beads `bif-bpfk.18` (EvidenceEnvelopeBuilder + bounded outbox, canary tests, <1% p99 regression) and `bif-kyy.16.5` are correct and well-specified.

**K7 — Kubernetes health probes convert control-plane incidents into pod churn.** *Verified:* single `/health` route (`transports/bifrost-http/handlers/health.go`) pings config/log/vector stores and 503s on failure; `disableDbPingsInHealth` defaults `false`; both Helm liveness and readiness point at `/health` (`helm-charts/bifrost/values.yaml:135,144,283`); Terraform mirrors it. Split `/livez` `/readyz` `/startupz`. This is the highest-certainty, lowest-effort fix in the whole corpus.

**K8 — Multimodal: the missing primitive is an authoritative model-aware capability registry, not another converter.** *Verified:* `grep` for any capability-registry type across `core transports plugins` returns **zero** matches; 55 provider files carry `NewUnsupportedOperationError` stubs (e.g. `core/providers/anthropic/anthropic.go`); the only capability source is the static test-account fixture matrix (`core/internal/llmtests/account.go`, ~540 boolean cells). The audit's core thesis — "an interface method is not capability evidence" — holds.

**K9 — Learning/eval/skill-promotion stays async and out of the availability path; protected Git + human approval is the only launch promotion authority.** Consistent across all files and the roadmap; no code contradicts it.

---

## 2. Disputed / unsupported claims (with code evidence)

These are the places where I break from the mode-file consensus. The direction of each finding survives; the mechanism or urgency does not.

### D1 — CORRECTION: "DumpBudgets writes absolute usage / last-writer-wins erasure" is mechanically wrong

**Who claims it:** A1-F1, B5-F02, F4-01, F7-02, I4-02, L1-03, L3-02, L5-F02, and (referenced) `MODE_OUTPUT_F4_L3.md`'s "multi-pod usage erasure." Repeatedly phrased as pods "directly overwrite usage fields from current local memory" and "the last writer can hide concurrent consumption."

**What the code actually does** (`plugins/governance/store.go:2194-2264`, `DumpBudgets`; `2104-2192`, `DumpRateLimits`):

1. It does **not** `Save` the row. It issues a **direct `Updates()` of only the usage columns** (`current_usage`, `last_reset`), inside `ExecuteTransaction`, with `SkipHooks`. The comments state this was deliberately built to *avoid* clobbering `max_limit`/`reset_duration` written by other nodes, and to avoid the read-then-write lock escalation that deadlocks. So the "overwrites config fields" and "SELECT+Save" framing is false.
2. The write is `newUsage = inMemoryBudget.CurrentUsage (+ baseline if present)`. There is a real delta-folding mechanism the mode files omit entirely: `LastDBUsagesBudgets` (`store.go:42-47,320-334`), which computes cross-node deltas as `CurrentUsage - LastDBUsage`.
3. **But** the tracker calls `DumpBudgets(ctx, nil)` and `DumpRateLimits(ctx, nil, nil)` (`plugins/governance/tracker.go:255,258,378,381`) — baselines are `nil` on the live periodic path. And the deadlock-swallow comment explicitly says "usage data will be synced via **gossip**" (`store.go:2254-2258`).

**The correct, narrower risk:** Each pod writes *its own local* `current_usage` absolute value. Cross-pod aggregation is not done by the DB write; it depends on the **gossip delta path** (`LastDBUsages*` + memberlist/gRPC counter-sync, `transports/config.schema.json:4958-5016`). The launch profile removes gossip (Aurora-only, no mandatory peer/Redis). **Therefore the real defect is: with gossip disabled, cross-pod usage does not aggregate at all, and periodic absolute writes race to last-writer-wins per row** — which is a *subset* of what the files claim, reached by a *different* mechanism than they describe. The recommended fix (reservations, `bif-kyy.4.9`) is unchanged and still correct. But any test written against the files' stated mechanism ("prove Save overwrites config fields") would test something the code already prevents, and any launch profile that *keeps* gossip on partially mitigates the very risk the files call unmitigated. **Get the mechanism right before writing the oracle.**

### D2 — CORRECTION: "Starlark nested MCP is the clearest pressure point / acquires connection before the gate as a distinctive outlier" is stale

**Who claims it:** H4-05 ("The Starlark nested path is the clearest pressure point… obtains the connection before running the plugin gate"), L3-04 (lists `executecode.go:471-488` as a separate worse path), L1-04 (implied).

**What the code actually does** (`core/mcp/codemode/starlark/executecode.go:471-495`): the Starlark path calls `AcquireClientConn` outside the gate **and then delegates to the same `RunWithPluginPipeline`**, with an in-code comment: *"mirroring the gateway's exec.go:prepareToolExecution → gate ordering… Keeps Starlark nested calls observationally identical to gateway-routed calls."*

**The correct characterization:** Starlark is **not** a distinctive or worse pressure point. It has *identical* ordering to the canonical `exec.go` path (K5). The MCP-ordering critique is architecturally valid for *both* paths equally — the connection is acquired before the mandatory gate everywhere — but the specific claim that Starlark is a uniquely dangerous outlier is false. **Consequence for planning:** the fix is *one* refactor of the shared `prepareToolExecution → gate` ordering, not a special-case Starlark hardening. `bif-bpfk.19`'s acceptance criteria must assert zero-side-effect on *both* entry points, but they are the same defect, not two.

### D3 — DISPUTE: F2's "remove `bif-kyy.4.6 -> bif-kyy.5.4`" is over-urgent and its P0 framing is wrong

**Who claims it:** F2-07 lists it as a "Confirmed wrong edge" alongside genuine P0-adjacent edits, and `MODE_OUTPUT_F2_H4.md:106+` item 4 repeats it.

**What the graph shows:** the edge exists (`bif-kyy.4.6 -> bif-kyy.5.4`, blocks), but `bif-kyy.4.6` (controlled-overdraft *approval workflow*) is **P1**, and its own text requires "approver RBAC." An approval workflow legitimately needs *some* principal/role mapping. The edit is defensible as "depend on the entitlement evaluator `bif-kyy.2.2` and budget-receipt `bif-kyy.4.7` rather than the *full* Okta group-to-model map `5.4`," but it is a P1 refinement, not a launch-critical correction, and it should not be batched with the true P0 gates. Listing it beside the real prerequisites inflates the apparent size of the "wrong edges" problem.

### D4 — UNSUPPORTED-AS-STATED: routing "fails open to unauthorized provider use"

**Who claims it (strong form):** F2-04/F4-03/L3-07 imply the empty-eligible-set soft-skip can cause *unauthorized* provider/model use.

**What the code shows:** the empty-eligible soft-skip (`plugins/governance/main.go:557-561`, returns `nil` with a TODO) is real and *does* undermine deterministic routing (wrong provider/cost/region lane) — that part is correct and P1. **But** authorization is still enforced downstream: `PreLLMHook` governance short-circuit runs (`main.go:1271-1310`), the governance provider allowlist is published so later layers cannot widen it (`main.go` allowlist, empty = deny-all), and the model-catalog resolver intersects with that allowlist. F4-03 concedes this ("not the same as bypassing all authentication"); the harder-edged framings in L3-07/F2-04 should be read down to "wrong-lane routing + weak auditability," not "unauthorized access." Severity P1, not P0.

### D5 — SCOPE OVERREACH RISK (meta): the corpus is internally redundant

Ten mode files re-derive the same seven blockers. L1-Risks ("analysis theater") names this hazard against itself. Three *non-requested* sibling files (`MODE_OUTPUT_B5_L5.md`, `F2_H4.md`, `F4_L3.md`) are cited *as roadmap authority* by the NTM files (e.g. F4 cites `B5_L5.md:109-124` as "roadmap requirement"). That is a citation smell: mode outputs are citing other mode outputs as if they were decided policy. Before any of these become executable oracles, promote the accepted claims into a single ADR set (the `bif-9w0.13` "convert findings into ADR experiments" bead already exists for this) and stop cross-citing peer analyses as authority.

---

## 3. Top five catastrophic launch risks

Ranked by (blast radius × likelihood-at-launch × how silently it fails). All are control-plane correctness failures on a healthy-looking data plane.

1. **Silent cross-pod overspend with no reservation and gossip disabled (K3 + D1).** With the Aurora-only launch profile, periodic absolute per-pod writes do not aggregate; N pods each admit against their own local view. Failure is invisible until the invoice. Worst case is unbounded, not "controlled overdraft." *Gate: `bif-kyy.4.9` + a three-pod concurrent-burst oracle asserting `admitted ≤ limit + approved_overdraft`.*

2. **Revoked key / deprovisioned identity stays live on a pod (K2 + K4).** No outbox/NOTIFY means propagation is unproven; a pod that misses an update keeps admitting a revoked VK while fleet metrics look green. Security-review-blocking. *Gate: `bif-kyy.6.7` stale-class table + drop-a-notification two-pod convergence-or-fail-closed test.*

3. **Mandatory guard fails open under fault (K2).** A transient resolver/parser/DB/classifier error in a control expressed as an ordinary plugin error becomes allow-by-default. *Gate: `bif-kyy.2.4` fault-injection (panic/timeout/corrupt-snapshot) asserting zero provider calls and zero MCP connection acquisition on deny.*

4. **MCP credential/connection side effect before denial (K5).** Denied privileged tool calls can still mint admin-level shared-connection headers (`mcp.go:126-143`) or open per-user transports before the gate. Confused-deputy exposure. *Gate: `bif-bpfk.19` sequence-conformance with fake credential store + fake transport, on both `exec.go` and Starlark entry points (D2).*

5. **Aurora/store incident amplified into a gateway outage by health probes (K7).** The one risk here that ships *today* with default charts. A control-plane hiccup restarts healthy serving pods, drains pools, loses warm snapshots. *Gate: split probes + a store-impairment K8s test proving liveness stays green while readiness degrades.*

(Privacy raw-content leakage (K6) is a sixth catastrophic risk but is contained by shipping metadata-only-hard-mode by default and disabling evidence consumers — see §5 G5 — so it is a gate, not an unmitigated launch risk.)

---

## 4. Smallest coherent implementation slice buildable and releasable now

The goal is a *truthful, narrow* v0.1 that is defensible under adversarial review, not a feature-complete enterprise gateway. Build exactly this, in order; each step is independently shippable and testable without the others landing first.

**Slice S0 — Availability truthfulness (days, not weeks).**
- Split `/livez` (process-only), `/readyz` (initialized providers + valid local snapshot), `/startupz` (boot/migration/snapshot acquisition). Update Helm + Terraform defaults. (K7)
- This is the only change that improves launch safety with essentially zero architectural risk. Do it first.

**Slice S1 — Mandatory decision membrane (the keystone).**
- A typed `AdmissionDecision` boundary (`allow | deny | stale_fail_closed | indeterminate_fail_closed | metadata_only`) that runs before provider I/O and before MCP connection acquisition, wrapping the *existing* governance checks — no new policy features. (K2, `bif-kyy.2.4`)
- Ship with the fault-injection conformance suite as the acceptance gate. This bead blocks the most others; landing it unblocks routing, MCP, and privacy work.

**Slice S2 — MCP policy-before-credential, shared-connection-only.**
- Reorder the *shared* `prepareToolExecution → gate` so mandatory policy precedes `AcquireClientConn`, on both `exec.go` and Starlark (D2). **Defer per-user OAuth MCP entirely** (B5-F05 Option B). Launch with static allow-lists and shared attenuated service credentials only. (K5, `bif-bpfk.19` partial)

**Slice S3 — Budget: reserve/settle for hard-dollar budgets only.**
- Aurora `budget_reservations` + settlement for the small set of *hard* budgets, keeping local counters as telemetry for soft budgets. Overshoot bound = outstanding leases + in-flight attempts + approved overdraft, proven by a three-pod test. (K3, `bif-kyy.4.9`). Overdraft *approval workflow* (`bif-kyy.4.6`, P1) is **out of this slice**.

**Slice S4 — Privacy hard-mode default + evidence consumers off.**
- Ship a `metadata_only` hard-mode flag that disables raw capture regardless of per-request override, and disable all eval/replay/proposal consumers of log tables. The full `EvidenceEnvelopeBuilder` (`bif-bpfk.18`) is *not* required for v0.1 *if* consumers are off. (K6, K9)

**Explicitly NOT in the slice:** Okta live integration beyond snapshot reconciliation, outbox/NOTIFY (poll-only is acceptable for v0.1 if the stale-class table is enforced and revocation fails closed), deterministic routing rework (keep it, but label current routing "best-effort, non-deterministic" — do not *claim* deterministic routing), the capability registry as a runtime authority (v0.1 ships a *static allowlist* per §5 G6), learned/adaptive routing, autonomous promotion, per-user MCP OAuth, Redis.

---

## 5. Go / No-Go gates for a truthful public v0.1

A "truthful" v0.1 is one whose public claims are all backed by a passing test. Each gate is No-Go until its oracle is green. The framing deliberately couples *what you may claim* to *what you have proven* — the launch risk is not missing features, it is **overstating the ones you have**.

- **G1 — Availability.** No-Go until `/livez` is proven independent of Aurora/log/vector stores and a store-impairment test keeps serving traffic alive. *Claim gated: "survives control-plane incidents."*
- **G2 — Fail-closed guard.** No-Go until fault-injection proves zero upstream effect on deny/indeterminate for LLM and MCP, streaming and non-streaming. *Claim gated: "enterprise access controls are mandatory."*
- **G3 — Budget bound.** No-Go until a three-pod concurrent burst (incl. one stream + one fallback + one pod crash pre-settlement) proves accepted spend ≤ `limit + approved_overdraft`. *Claim gated: "controlled overdraft." Until then, claim only "post-hoc usage accounting," which is what the code does.*
- **G4 — Revocation convergence.** No-Go until a two-pod test with a dropped notification proves the isolated pod either converges within the stated bound or fails closed for protected traffic. *Claim gated: any revocation-time SLA.*
- **G5 — Privacy.** No-Go until a canary suite (secrets in headers, body, tool args/results, plugin logs, stream chunks split across boundaries) proves durable logs/issues/MRs contain only approved metadata under default config. *Claim gated: "privacy-safe traces/evals."*
- **G6 — Multimodal honesty.** No-Go until every advertised provider/model/operation cell is backed by a passing credentialed live test, and unsupported stubs have negative tests and are hidden from UI/docs. Ship a **static allowlist**, not a claim of uniform multimodal support. *Claim gated: every cell in the provider/feature matrix.* (multimodal audit §"Credentialed release matrix")
- **G7 — Release reproducibility.** No-Go until `bif-kyy.14.1` produces a reproducible upstream build + release gap ledger (Apache NOTICE/modification duties, branding, SBOM, signing). The bead's own instruction — *"stop rather than claiming release readiness when the baseline is not reproducible"* — is the correct default. A public v0.1 with unverified license/attribution provenance is a No-Go regardless of technical readiness.

---

## 6. Exact Bead dependency / priority corrections

Verified against the live graph (`br show`). Recommendations for human review only — **I did not modify Beads.**

**Confirmed-correct edges (do not touch):** `bif-kyy.2.4` → its dependents (MCP firewall `.15.3`, sanitized sinks `.16.5`, routing `.7.1`, three-pod slice `.14.3`) are all right. `bif-bpfk.19 -> bif-bpfk.12` (evidence trust before MCP receipts) is right. `bif-kyy.4.9`'s dependents (`.4.5`, `.4.2`, `cks.3`) are right.

**Priority corrections:**
- `bif-kyy.4.6` (overdraft approval workflow) is correctly **P1** and must **not** be pulled onto the P0 critical path (contra the urgency implied by F2-07). Its `-> bif-kyy.5.4` edge is defensible for an approval workflow; the F2/F2_H4 recommendation to remove it is a P1 refinement, not a launch blocker (D3). **Recommend: leave the edge; do not batch this edit with P0 gates.**
- The genuine P0 critical path is: `bif-kyy.2.4` (membrane) → gates `bif-bpfk.19` (MCP), `bif-kyy.7.1` (routing), `bif-kyy.16.5` (sinks). Independently, `bif-kyy.4.9` (reservations) and `bif-kyy.6.7`/`bif-kyy.6.8` (stale semantics + outbox). These are already P0 and already ready — the graph is structurally sound here.

**Missing-edge recommendations (add, pending review):**
- Make `bif-kyy.6.8` (outbox) / `bif-kyy.6.4` (propagation choice) **block** cross-pod consumers: VK mutation enforcement, entitlement compiler publication, routing-policy mutation, MCP grant publication. Today these are not gated on the substrate that must carry them.
- Extract a **shared** MCP policy-before-credential invariant so `bif-bpfk.19` does **not** require stateful failover `bif-kyy.15.18` first (F2-07 is right on this one): proving "denied call issues zero credentials" is a smaller, earlier gate than sticky connection ownership. The live graph has `bif-kyy.15.18 -> bif-bpfk.19` only via shared dependents, not a hard block — good; keep it that way and resist adding a `.15.18 → bpfk.19` hard edge.

**Do NOT apply (contra some mode files):**
- Do not restructure the graph around the Starlark path as a separate MCP risk (D2) — it is the same defect as `exec.go`.
- Do not add oracles that assert `DumpBudgets` overwrites config fields (D1) — the code already prevents that; the oracle would pass trivially and mislead.

**Scope guard (verified):** `MODES_ANALYSIS_PROGRESS.md:46` — "Do not expand launch scope back into autonomous marketplace promotion." Keep `bif-bpfk.14/.15/.16/.17/.21/.22/.23/.25/.26` and autonomous-promotion beads post-launch. The graph currently respects this; keep it.

---

## 7. Base-repo verdict: extend Bifrost vs net-new

**Extend Bifrost. This is not a close call, and the dissent does not change it.**

The reasons are structural and code-verified, not sentiment:

1. **The expensive, correct parts already exist.** Multi-provider dispatch, streaming accumulation, the plugin pipeline, governance evaluation, MCP execution, tracing/logging, the config store, and a real (non-mock) provider test harness are all present and coherent. The multimodal audit's inventory is accurate: replacing this discards substantial working code for no correctness gain.

2. **Every launch gap is additive, not corrective.** The seven consensus blockers (K2–K8) are all *new seams around* the existing substrate — a mandatory membrane, a reservation ledger, an outbox, a privacy envelope, split probes, a capability registry, reordered MCP. None require ripping out or rewriting the data plane. A net-new build would re-implement the substrate *and* still owe every one of these seams.

3. **The substrate's shape already matches the target.** Atomic-pointer runtime replacement, off-context stream accumulation, and process-local hot reads are exactly the primitives the snapshot/reservation design wants (L5-F03 is right about this). The gap is a *publication protocol* over primitives that exist, not missing primitives.

**The one genuine caveat — and it is a business/legal gate, not a technical one:** the extend-vs-net-new decision is *conditional on `bif-kyy.14.1` passing* (G7). If the upstream build is not reproducible, or Apache NOTICE/modification/attribution/branding duties cannot be satisfied for a public fork, then "extend" is blocked for reasons that have nothing to do with code quality. That bead is correctly P0 and correctly instructed to *stop rather than claim readiness*. Technical verdict: extend. Release verdict: extend **iff** the provenance ledger is clean.

---

## Appendix — Verification ledger (what I checked myself)

| Claim | Source files | My check | Result |
|---|---|---|---|
| Aurora outbox/NOTIFY absent | A1-F4, B5-F03, F2-03, K4 | `grep pg_notify/LISTEN/outbox` in `.go` | **0 matches — confirmed absent** |
| gossip/counter-sync present in code, not launch profile | A1-F4 | `config.schema.json:4958-5016` | Confirmed (mesh/gossip + gRPC counter-sync exist) |
| Plugin errors non-blocking; only PreLLM short-circuit denies | K2 (all) | `plugin.go:192-294`, `bifrost.go:7300-7338`, `main.go:1271-1310` | Confirmed |
| Settlement post-hoc, no pre-provider reserve | K3 (all) | `main.go PostLLMHook`, `budget.go` schema | Confirmed |
| "DumpBudgets absolute overwrite / last-writer erasure" | A1-F1,F4-01,I4-02,L3-02,L5-F02 | `store.go:2104-2264` | **Mechanically wrong — direct Updates() of usage cols only + LastDBUsages gossip delta; baselines nil on live path (D1)** |
| MCP connection before gate | K5 (all) | `exec.go:82-124`, `mcp.go:126-143` | Confirmed |
| Starlark is a distinctive worse MCP path | H4-05, L3-04 | `executecode.go:471-495` | **Stale — mirrors exec.go, observationally identical (D2)** |
| Single `/health` pings stores; both probes | K7 (all) | `health.go`, `values.yaml:135,144,283` | Confirmed |
| No capability registry; stubs are not capability | K8, audit | `grep` registry (0), 55 stub files | Confirmed |
| `bif-kyy.4.6 -> 5.4` is a launch-critical wrong edge | F2-07 | `br show bif-kyy.4.6` (P1) | **Over-urgent — 4.6 is P1, off P0 path (D3)** |
| Routing soft-skip → unauthorized provider use | F2-04, L3-07 (strong form) | `main.go:557-561` + allowlist/PreLLM | **Read down to wrong-lane + weak audit, P1 (D4)** |
