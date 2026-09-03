# Franken ecosystem fit for the FrankenGate control plane

Status: architecture and dependency decision record, 2026-07-18.

## Executive decision

The Franken ecosystem contains several strong conceptual matches for FrankenGate, but it must not become a bundle of mandatory services. The operational objective remains fewer moving pieces: Go inference data plane, Go analytics service, ClickHouse projections, object storage for large artifacts, and optional workers selected by proven workload.

The intended operator and beneficiary is Brandon, using the system independently—not OpenAI or Anthropic. Merely using an OpenAI coding model does not by itself make Brandon, FrankenGate, or every artifact produced with that model an OpenAI affiliate, contractor, representative, or project operated for OpenAI's benefit. The rider still matters, but it must be applied to the actual actor, use, packaging, and distribution path rather than treated as a blanket ban triggered by the development tool.

The preferred strategy is to consume independently published FrankenSuite releases as external executables, containers, or services and orchestrate them through stable protocols. This preserves Dicklesworthstone's release velocity, keeps upstream code and licensing intact, and avoids turning FrankenGate into a derivative monolith. Three adoption modes must remain distinct:

1. **External orchestration:** Helm references an official upstream image/binary or an operator-supplied endpoint. FrankenGate does not copy or modify upstream code. Record version, digest, license, configuration, health, and protocol compatibility. This is the default.
2. **Linked library:** a Franken crate is compiled into a FrankenGate-owned binary. The full transitive license closure and rider apply to the resulting distribution; notices, source obligations, compatibility, and product licensing require explicit review.
3. **Vendored or modified derivative:** FrankenGate copies or modifies upstream code. Preserve the upstream license/rider and attribution in the derivative and distribution, and do not describe the combined artifact as unqualified Apache-2.0. This needs owner/legal approval before implementation.

This report is an engineering/provenance decision, not legal advice. Exact rider applicability and combined-work licensing should be reviewed for the intended entity and distribution. Meanwhile, external orchestration lets us evaluate and use upstream releases without copying them into FrankenGate. For code linked into the core Rust control-plane binary, Axum, Tokio, SQLx/PostgreSQL, Serde, OpenTelemetry, and generated OpenAPI remain the low-risk baseline. Do not spend the implementation budget building a second Asupersync/FastAPI Rust/SQLModel Rust control plane. Revisit that stack through a narrow vertical spike only when an upstream release closes a concrete baseline gap or materially reduces owned code.

## Method and scope

The inventory covers all repositories in the Dicklesworthstone account whose names or descriptions contained `franken` on 2026-07-18: 30 repositories. Stable releases were preferred over `main`. The follow-up pass inspected release/source architecture and protocol surfaces under Brandon's stated independent-use context; it did not treat use of an OpenAI development model as a restricted-party fact. Adjacent substrates were added where a Franken composition depends on them. Two permissive entry points were also checked at stable tags:

- `franken-agent-detection` v0.1.9, commit `a2a190cbfe04c7266102484443701c4834a162c6`.
- `fastapi_rust` v0.3.0, commit `7adff35ba0f71f31bc9381d7ab91acc139102c13`; technically adjacent rather than Franken-named, but relevant to the Rust API decision.

“Evaluate all permutations” cannot responsibly mean enumerating every subset of 30 projects (`2^30` combinations). The useful unit is a capability composition: storage, runtime, API, retrieval, graph, memory, untrusted execution, media ingestion, rendering, operator tooling, and development tooling. The composition analysis below covers every meaningful cross-capability bundle while rejecting combinations that duplicate authority or mix incompatible trust and scaling domains.

## Individual project disposition

| Project | Declared role | FrankenGate fit | Decision |
|---|---|---|---|
| `beads-for-frankentui` | Static Beads graph dashboard | Development visualization only; duplicates product dashboard | Do not ship; existing `br`/`bv` remains planning tooling |
| `beads_for_franken_engine` | Static FrankenEngine Beads dashboard | No runtime value | Do not adopt |
| `eidetic_engine_cli` v0.12.0 | Local explainable agent memory over several Franken substrates | Strong fit for endpoint-local/private trace recall and skill mining | Evaluate as an external local tool; PostgreSQL remains managed evidence authority |
| `franken_agent_detection` v0.1.9 | Deterministic local coding-agent discovery | High fit in an endpoint collector bootstrap path | Approve a bounded bakeoff using default features only; never run in gateway pods |
| `franken_engine` v0.1.0 | Adversarial extension runtime, replay, receipts, containment | Strong fit for unsafe evaluator/plugin workers | Evaluate as an isolated external runner behind the job protocol |
| `franken_markdown` v0.3.4 | Rust Markdown to HTML/PDF | Optional report rendering worker | Evaluate as a separate report-rendering binary; never gateway hot path |
| `franken_markdown_website` | Product/demo website | None | Do not adopt |
| `franken_networkx` v0.2.0 | Deterministic graph algorithms | Skill dependency graphs, lineage, bottleneck analysis | Evaluate as an offline graph worker after PostgreSQL baseline |
| `franken_node` v0.1.0 | Trust-oriented JavaScript/TypeScript runtime | Potential code-scorer sandbox | Evaluate only as an isolated external runner, never inside the control API |
| `franken_numpy` v0.2.0 | NumPy compatibility | Numerical evaluator/training substrate | Optional worker-image component; compare compatibility with Python NumPy |
| `franken_ocr` v0.7.2 | CPU-only OCR | Optional document-evidence ingestion | High-value optional CPU worker with separate privacy/model policy |
| `franken_snowflake` v0.0.1 | Snowflake SQL API connector | Enterprise export/import adapter | External adapter candidate when customer demand justifies its early maturity |
| `franken_whisper` v0.5.0 | ASR orchestration | Optional audio evidence ingestion | Optional media worker, outside launch scope but architecturally clean |
| `frankenfs` v0.2.0 | FUSE ext4/btrfs replacement | No product need | Reject; Kubernetes volumes/object stores remain infrastructure authority |
| `frankengraphdb` | Proposed property graph database | Lineage/skill graph storage | No tagged implementation; watch, but do not add another authority yet |
| `frankenjax` | JAX compatibility | Training/research worker only | External experimental training worker; Python/JAX remains compatibility baseline |
| `frankenlibc` | glibc interposition/safety membrane | Possible sandbox hardening experiment | Defer; far below the application boundary and increases incident complexity |
| `frankenmermaid` v0.2.0 | Mermaid-compatible diagrams | Report visualization | Optional external renderer; browser rendering is simpler initially |
| `frankenpandas` v0.1.2 | pandas compatibility | Eval result transformations | External worker candidate; never control-API dependency |
| `frankenredis` | Redis compatibility | Optional cache/queue accelerator | Evaluate only as a non-authoritative external accelerator after PostgreSQL evidence |
| `frankenscipy` | SciPy compatibility | Statistical/scientific evaluators | Optional scorer-worker component with differential conformance |
| `frankensearch` v1.2.5 | Two-tier BM25/vector hybrid retrieval | Strong fit for authorized trace, skill, and evidence retrieval | Priority external sidecar/service bakeoff; pgvector remains authority and fallback |
| `frankensim` | Simulation/optimization/rendering continuum | Robotics/world-model research jobs | Future isolated research worker; no control-plane coupling |
| `frankensim_website` | Product/demo website | None | Do not adopt |
| `frankensqlite` v0.1.17 | SQLite replacement | Local collector cache or CLI state | Evaluate endpoint-local spool only; never replace PostgreSQL server authority |
| `frankensqlite_website` | Product website | None | Do not adopt |
| `frankenterm` | WezTerm agent-fleet hypervisor | Development-time swarm observation | Adopt externally for development operations where useful; never Helm runtime dependency |
| `frankentorch` | PyTorch compatibility | Training/inference workers | External experimental worker; official PyTorch remains compatibility baseline |
| `frankentui` | Terminal UI kernel | Operator/collector CLI UX | Candidate for separate operator/collector CLI, not the web dashboard |
| `frankentui_website` | Product website and Beads visualization | None | Do not adopt |

## Source and release-readiness findings

The project names are not interchangeable with deployable services. The important technical distinctions are:

| Project or family | What the inspected release/source provides | Hard integration constraint | Adoption lane |
|---|---|---|---|
| Frankensearch v1.2.5 | `fsfs` CLI and Rust crates; Tantivy BM25, vector search, fusion/reranking, progressive results, durable local storage, JSON/JSONL/TOON/CSV, doctor and watch workflows | No production HTTP/multi-tenant/auth service or Helm packaging was found. FSVI uses memory-mapped f16 vectors and optimized brute-force; ANN is optional, so capacity must be proven on FrankenGate corpora. | P0 bakeoff behind a thin authorized adapter; upstream distribution remains independently replaceable |
| Eidetic Engine v0.12.0 | Endpoint-local typed memory, hybrid search, graphs, provenance, deterministic hashes, redaction classes and context packs | CLI-first. The documented `serve` surface is reserved/future, not a managed multi-tenant service. | P1 endpoint-local collector/skill tool |
| Asupersync v0.3.9 | Structured concurrency, capability context, regions, budgets and deterministic concurrency laboratory | A novel, broad runtime raises operator and migration risk even where its semantics are attractive. | Watch and borrow test/orchestration concepts; spike only for a measured gap |
| FastAPI Rust v0.3.0 | Asupersync-native typed routing, extractors and OpenAPI | Upstream describes it as early development; OpenAPI is minimal, TCP hardening is evolving, WebSockets are partial and HTTP/2 is absent. | Challenger only, not initial public API default |
| SQLModel Rust v0.3.0 | Typed models, queries, sessions, pooling, transactions and migrations across several databases | Nightly Rust and evolving API/documentation; it shares the Asupersync stack's correlated upgrade surface. | Challenger; explicit SQL migrations and SQLx remain control |
| FrankenEngine v0.1.0 | Sandboxed extension concepts, adversarial replay and receipts | Stable source referenced absolute local `/dp/...` dependencies and does not yet prove a clean independently reproducible distribution; same-runtime multi-tenant isolation is incomplete. | Watch/bake off only after clean-build and isolation proof |
| FrankenNode v0.1.0 | Trust cards, revocation, replay, fleet quarantine, signed registry and capability-token concepts | Large correlated substrate and partial migration/isolation story. | Future isolated JavaScript scorer, never API process |
| FrankenNetworkX v0.2.0 | Deterministic graph algorithms and Python compatibility | Expected overhead on tiny graphs; managed service behavior is outside its scope. | P1 offline skill/lineage graph jobs after PostgreSQL recursive-query baseline |
| MetaSkill v0.1.5 | Skill validation, testing, pruning, quarantine, MCP, SQLite/Git/Tantivy and deterministic hybrid retrieval | Endpoint/developer workflow, not a tenant authority. | P1 external skill authoring and promotion tool |
| CASS / coding-agent-session-search | Local session indexing, bookmarks, robot output, recovery and optional semantic model | Local raw sessions are highly sensitive and must not be uploaded by default. | P1 collector source with explicit review/redaction |
| FrankenMarkdown v0.3.4 + FrankenMermaid v0.2.0 | Deterministic report and diagram rendering with machine-readable diagnostics | PDF pagination and browser-complete SVG compatibility still need output conformance tests. | P1 report-worker bundle |
| FrankenTUI v0.5.0 | Deterministic diff rendering, inline mode, widgets and terminal cleanup | API/publication/compatibility matrix remains incomplete. | CLI UX only |
| FrankenTerm v0.12.0 | Passive-first WezTerm fleet observation and robot output | Deliberately WezTerm-specific; remote text and browser automation are incomplete. | External developer tooling only |
| FrankenSQLite v0.1.17 | SQLite-compatible local engine with page-level MVCC/SSI | It is not PostgreSQL, does not provide row-level locking, and adds a second database implementation to operate/test. | Endpoint spool experiment only |
| FrankenRedis | Redis-compatible accelerator with strict/hardened modes | Logical databases are explicitly not tenant isolation; no stable tagged release was found. | Optional non-authoritative accelerator only |
| FrankenSnowflake v0.0.1 | Snowflake SQL/API authentication and redaction paths | Early release with absolute local dependency references and no deployable service packaging found. | Customer-driven export adapter only |
| FrankenOCR v0.7.2 | CPU-focused OCR with local model choices and quantization | Model size, cold start, privacy, accuracy and CPU cost require a dedicated worker benchmark. | Optional document worker |
| FrankenWhisper v0.5.0 | ASR orchestration and release/test tooling | Orchestrates backend choices rather than eliminating their model/runtime operations. | Optional audio worker |
| NumPy/Pandas/SciPy/JAX/Torch compatibility family | Potential Rust numerical/eval execution backends | Differential compatibility, CUDA/model ecosystem and clean release evidence vary; the inspected FrankenTorch checkout was insufficient for a source-backed claim. | Experimental worker images; official Python stacks remain oracle |
| FrankenSim | Broad simulation/optimization research substrate | Very large, untagged workspace and unrelated scaling profile. | Research-only future worker |
| FrankenGraphDB | Design/plan for a graph database | No tagged executable implementation was found. | Watch only |
| FrankenFS + FrankenLibc | Filesystem/libc replacement and safety substrates | Wrong application boundary, substantial kernel/unsafe-code incident surface, no demonstrated FrankenGate requirement. | Reject |

These lanes are technical, not judgments about the author's quality or velocity. An upstream component can be excellent and still belong behind a job/protocol boundary because its workload, trust domain, or scaling signal differs from the gateway.

## Adjacent substrate disposition

These are not all Franken-named, but they determine whether a proposed bundle is actually usable.

| Project | Potential role | Decision |
|---|---|---|
| Asupersync v0.3.9 | Structured-concurrency runtime for the Rust control plane | Evaluate in a separate-binary control-plane bakeoff against Tokio; do not vendor casually. |
| `sqlmodel_rust` v0.3.0 | Typed PostgreSQL model/query layer | Evaluate with the coherent stack; SQLx remains the maturity/control baseline. |
| Beads Rust / Beads Viewer | Planning and dependency graph | Adopt as external development tooling; never product runtime or customer data store. The emerging `beads_viewer_rust` static pages exporter may supply the roadmap/DAG browser surface after a stable release, avoiding a custom viewer. |
| NTM / FrankenTerm | Agent development orchestration | External build/research tooling only; never Helm dependency. |
| CASS / Eidetic / coding-agent-session-search | Local session recall and mining | Strong external endpoint-tool candidates; managed collector protocol remains implementation-independent. |
| Agent Mail | Multi-agent development coordination | Development-time only; no product control-plane dependency. |
| DCG / UBS | Developer safety and static scanning | CI/developer tooling only, subject to license policy; not a customer runtime component. |
| RaptorQ-based durability ideas | Repairable artifact transport/storage | No need for the launch control plane. Object-store checksums, replication, versioning, and signed manifests are simpler. |

## Composition analysis

### 1. Production Rust control plane

Proposed safe bundle:

```text
Ingress / one product origin
  -> Axum HTTP API on Tokio
      -> generated OpenAPI contracts
      -> SQLx -> PostgreSQL metadata, RLS, outbox, leases
      -> signed object-store URLs and immutable manifests
      -> workload-class queues -> isolated workers
```

This is one service binary plus worker binaries from one Rust workspace. It provides an ecosystem with mature licensing and operations while retaining the required bounded task trees, cancellation propagation, supervision, capability tokens, deterministic tests, and typed terminal outcomes.

Alternative bundle: `fastapi_rust + Asupersync + sqlmodel_rust`. Its advantages are a coherent cancellation model, deterministic concurrency testing, generated API ergonomics, and rapid coordinated upgrades; its risks are early maturity, correlated ecosystem changes, smaller operator experience, and combined rider obligations. Do not build it in parallel. Track upstream releases and authorize one time-boxed vertical spike only if it can remove a measured baseline limitation or a meaningful amount of FrankenGate-owned lifecycle code. The spike must reuse the same PostgreSQL schema and job protocol and have a predeclared stop decision, so it cannot become a shadow production implementation.

### 2. Authorized retrieval and agent memory

Desired conceptual flow:

```text
PostgreSQL evidence authority + RLS
  -> durable outbox
  -> redaction / eligibility worker
  -> versioned derived lexical/vector index
  -> retrieval API reauthorizes and intersects candidate IDs
  -> citations point back to immutable PostgreSQL records
```

`Frankensearch + Eidetic + FrankenNetworkX` covers hybrid retrieval, endpoint memory, and graph traversal. The strongest composition keeps them independently upgradeable: Eidetic runs endpoint-local; an adapter process invokes or links the pinned Frankensearch release and exposes the FrankenGate retrieval contract; FrankenNetworkX runs offline graph jobs. PostgreSQL remains policy/evidence authority. Promote each component independently so a correlated ecosystem update cannot force an all-at-once rollout.

The adapter is required because the inspected Frankensearch release is not itself a tenant-aware HTTP service. It must enforce identity, purpose, tenant/classification scope and policy epoch before returning any candidate or progressive phase; isolate indexes and model caches; expose readiness, metrics and bounded concurrency; accept outbox rebuild/tombstone operations; and retain PostgreSQL source IDs for reauthorization and citation. A Helm chart may run it disabled, as a dedicated Deployment, or point to an operator-managed endpoint. It must not be an inference-container sidecar merely for deployment convenience.

### 3. Evaluator and training plane

`FrankenEngine + FrankenNode + FrankenNumPy/Pandas/SciPy/JAX/Torch` describes a compelling all-Rust evaluator/training environment, but it should remain a portfolio of external worker images behind one job protocol. FrankenEngine/FrankenNode are sandbox candidates; numerical projects are optional execution backends selected per evaluator. Python/CUDA remains the compatibility baseline until differential tests prove a given Franken backend. The control plane stores specifications, leases, checkpoints, receipts, and results; it does not link every numerical runtime into itself.

### 4. Endpoint collector and personal skill mining

Approved bounded composition:

```text
MIT franken-agent-detection (default features)
  -> independently written collector adapters
  -> encrypted local spool using standard SQLite or files
  -> explicit user review/redaction
  -> short-lived device authorization
  -> governed asynchronous analytics API
```

This crate adds real value by eliminating repeated, drifting installation probes across Claude Code, Codex, Gemini, and other collectors. Default features are the smallest initial integration. FrankenSQLite-backed connector features may be evaluated separately with their full license and compatibility closure. Detection is not authorization, proof of ownership, session parsing, continuous watching, or consent; those remain explicit collector responsibilities.

### 5. Document, audio, and report enrichment

`FrankenOCR + FrankenWhisper + FrankenMarkdown + FrankenMermaid` is a plausible enrichment pipeline but not a gateway capability. Each remains an independently versioned worker with distinct model, privacy, CPU, and artifact requirements. A report job can fan out OCR/ASR, then render Markdown/diagrams, but none deploy in inference or analytics API pods.

### 6. Storage and durability replacement stack

`FrankenSQLite + FrankenRedis + FrankenFS + FrankenGraphDB + RaptorQ` must not replace the managed platform as a bundle. Selective external use is possible—FrankenSQLite for endpoint-local spool, FrankenRedis as a non-authoritative accelerator, RaptorQ for hostile-network artifact transport—but PostgreSQL, object storage, and Kubernetes volumes remain managed authorities. FrankenFS and FrankenGraphDB require a separate demonstrated problem before adoption.

### 7. Operator and developer experience

`FrankenTUI + FrankenTerm + Beads viewers + NTM` can improve development workflows but must stay outside Helm and the customer security boundary. The web dashboard remains the uniform product interface. A future CLI may consume the same public API, but the UI library is selected independently under compatible licensing. Do not build a custom Beads dependency viewer while `beads_viewer_rust` is converging on self-contained static page export, preview/watch mode, deployment assistance and multi-repository workspace graphs. Re-evaluate its first stable release as a generated read-only roadmap surface. It complements rather than replaces the runtime/AWS architecture diagram because an issue DAG does not encode traffic, trust or deployment boundaries.

### 8. Snowflake and enterprise data exchange

FrankenSnowflake should not be embedded into the control plane. If a customer requires warehouse export, implement an asynchronous adapter behind the artifact/export protocol with a separate credential, egress, quota, and audit boundary. Prefer standard Snowflake APIs/drivers with compatible support and licensing.

## Permutation rules

The following rules cover meaningful combinations without enumerating useless subsets:

1. Exactly one authority per datum. Derived search, graph, cache, and memory systems never become policy or evidence authority.
2. No experimental dependency on the inference hot path.
3. Separate query serving from index building, and API admission from job execution.
4. Combine libraries inside one binary only when they share scaling, trust, and failure domains. Otherwise compose through a versioned job or HTTP contract.
5. Evaluate the license and rider across the actual actor, external-service versus linked-library boundary, transitive closure, modification, and redistribution path.
6. Product runtime, optional Helm component, sandboxed job image, endpoint-local tool, CI tool, and research reference are different adoption classes and require different proof.
7. Every optional accelerator must have an authority-preserving fallback and rebuild path.
8. Numerical/media compatibility projects belong in worker images, never the Rust control API.
9. Websites and Beads viewers are not reusable backend architecture.
10. No combination advances from research until the exact stable-tag closure passes the provenance and redistribution gate.
11. Prefer an official upstream binary/image when one exists. If only crates or a CLI exist, keep the smallest FrankenGate-owned adapter possible and prove clean reproducible builds; do not fork upstream merely to create a service facade.
12. Upgrade upstream components independently through pinned digests, compatibility tests, shadow traffic, canaries and rollback. A coordinated ecosystem release is not an excuse for an all-at-once production rollout.

## Recommended decisions by horizon

### Now

- Keep analytics-go behind an explicit service boundary with bounded cancellation, tenant isolation, and retention contracts.
- Preserve the Go gateway and one-origin dashboard architecture.
- Keep pgvector/PostgreSQL as the authorized retrieval default.
- Add an adoption-mode and license/provenance gate before every Franken integration Bead.
- Prototype `franken-agent-detection` default features in the endpoint collector only after dependency/SBOM verification.

### After measured need

- Benchmark the official Frankensearch distribution through the minimum authorized adapter against the already-existing PostgreSQL retrieval path; do not build a second feature-complete backend merely for comparison.
- Add sandboxed Python/WASM evaluator workers and customer-required warehouse/media adapters.
- Add a separate static dashboard deployment without fragmenting browser authentication.

### When linking, modifying, or redistributing rider-licensed components

- Determine the intended operating entity and whether the combined work is a derivative or redistribution; obtain owner/legal approval where needed.
- Preserve the exact upstream license/rider and attribution, and make the combined artifact's licensing explicit rather than calling it unqualified Apache-2.0.
- Pin, verify, conformance-test, canary, and independently roll back every upstream component.

## Sources

- [Dicklesworthstone repositories](https://github.com/Dicklesworthstone?tab=repositories)
- [Frankensearch license](https://github.com/Dicklesworthstone/frankensearch/blob/main/LICENSE)
- [franken-agent-detection v0.1.9](https://github.com/Dicklesworthstone/franken_agent_detection/releases/tag/v0.1.9)
- [fastapi_rust v0.3.0](https://github.com/Dicklesworthstone/fastapi_rust/releases/tag/v0.3.0)
- [Axum v0.8.9](https://github.com/tokio-rs/axum/releases/tag/axum-v0.8.9)
- [Tokio v1.53.0](https://github.com/tokio-rs/tokio/releases/tag/tokio-1.53.0)
- [SQLx repository](https://github.com/transact-rs/sqlx)
