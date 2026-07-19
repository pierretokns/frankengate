# Franken ecosystem fit for the FrankenGate control plane

Status: architecture and dependency decision record, 2026-07-18.

## Executive decision

The Franken ecosystem contains several strong conceptual matches for FrankenGate, but it must not become a bundle of mandatory services. The operational objective remains fewer moving pieces: Go inference data plane, PostgreSQL authority, a separately scalable Rust analytics control plane, object storage for large artifacts, and optional workers selected by proven workload.

Only one explicitly Franken-named library is presently eligible for direct evaluation and narrowly useful: `franken-agent-detection`, under plain MIT, with default features only. Nearly every other code repository carries an “MIT with OpenAI/Anthropic Rider.” That rider denies OpenAI, Anthropic, affiliates, and anyone acting for them all rights, explicitly including analysis, execution, testing, benchmarking, indexing, and incorporation. Those projects are therefore blocked for this OpenAI-assisted development effort and incompatible with FrankenGate's Apache-2.0 redistribution unless the copyright holder grants written permission or publishes a compatible license.

This is both a legal and architectural boundary:

- Do not copy, vendor, link, execute, benchmark, translate, or derive implementation from rider-licensed code.
- Public repository metadata and declared product roles may inform a capability map, but not implementation.
- A similarly named or separately MIT wrapper is not sufficient if its transitive dependency is restricted. `fastapi_rust` is MIT/Apache-2.0 but depends on rider-licensed Asupersync, so the deployable stack remains blocked.
- Optional features of an otherwise MIT crate must be checked individually. `franken-agent-detection` default features are ordinary permissive dependencies; its SQLite connector features depend on rider-licensed FrankenSQLite and are excluded.
- Every future adoption requires a pinned release, dependency closure, SPDX/license evidence, SBOM entry, source digest, conformance tests, and rollback plan.

Absent relicensing, the production Rust baseline should be a conventional permissive stack: Axum, Tokio, SQLx/PostgreSQL, Serde, OpenTelemetry, and a generated OpenAPI contract. Franken-inspired properties—structured ownership, bounded cancellation, typed outcomes, deterministic scheduling tests, capability-scoped effects, receipts, and rebuildable indexes—remain architectural requirements, implemented independently.

## Method and scope

The inventory covers all repositories in the Dicklesworthstone account whose names or descriptions contained `franken` on 2026-07-18: 30 repositories. Stable releases were preferred over `main`. Technical source inspection stopped at the license boundary. The two plain-MIT candidates were checked at their stable tags:

- `franken-agent-detection` v0.1.9, commit `a2a190cbfe04c7266102484443701c4834a162c6`.
- `fastapi_rust` v0.3.0, commit `7adff35ba0f71f31bc9381d7ab91acc139102c13`; technically adjacent rather than Franken-named, but relevant to the Rust API decision.

“Evaluate all permutations” cannot responsibly mean enumerating every subset of 30 projects (`2^30` combinations). The useful unit is a capability composition: storage, runtime, API, retrieval, graph, memory, untrusted execution, media ingestion, rendering, operator tooling, and development tooling. The composition analysis below covers every meaningful cross-capability bundle while rejecting combinations that duplicate authority or mix incompatible trust and scaling domains.

## Individual project disposition

| Project | Declared role | FrankenGate fit | Decision |
|---|---|---|---|
| `beads-for-frankentui` | Static Beads graph dashboard | Development visualization only; duplicates product dashboard | Do not ship; existing `br`/`bv` remains planning tooling |
| `beads_for_franken_engine` | Static FrankenEngine Beads dashboard | No runtime value | Do not adopt |
| `eidetic_engine_cli` v0.12.0 | Local explainable agent memory over several Franken substrates | Conceptually close to private trace recall and skill mining | Rider-blocked; retain our canonical evidence and PostgreSQL design |
| `franken_agent_detection` v0.1.9 | Deterministic local coding-agent discovery | High fit in an endpoint collector bootstrap path | Approve a bounded bakeoff using default features only; never run in gateway pods |
| `franken_engine` v0.1.0 | Adversarial extension runtime, replay, receipts, containment | Conceptual fit for unsafe evaluator/plugin workers | Rider-blocked; use container/WASM sandbox protocol and independent receipts |
| `franken_markdown` v0.3.4 | Rust Markdown to HTML/PDF | Optional report rendering worker | Rider-blocked and non-core; use current web rendering or a permissive renderer |
| `franken_markdown_website` | Product/demo website | None | Do not adopt |
| `franken_networkx` v0.2.0 | Deterministic graph algorithms | Skill dependency graphs, lineage, bottleneck analysis | Rider-blocked; use PostgreSQL recursive queries initially and permissive offline graph libraries only after benchmark |
| `franken_node` v0.1.0 | Trust-oriented JavaScript/TypeScript runtime | Potential code-scorer sandbox | Rider-blocked; do not place arbitrary JS in control API; use isolated job images/WASM |
| `franken_numpy` v0.2.0 | NumPy compatibility | Numerical evaluator/training substrate | Rider-blocked and unnecessary; Python evaluator containers retain NumPy |
| `franken_ocr` v0.7.2 | CPU-only OCR | Optional document-evidence ingestion | Rider-blocked; also a distinct model/CPU workload requiring a separate worker and opt-in data policy |
| `franken_snowflake` v0.0.1 | Snowflake SQL API connector | Enterprise export/import adapter | Rider-blocked and immature; defer until a customer requires Snowflake |
| `franken_whisper` v0.5.0 | ASR orchestration | Optional audio evidence ingestion | Rider-blocked and outside the gateway/eval launch scope |
| `frankenfs` v0.2.0 | FUSE ext4/btrfs replacement | No product need | Reject; Kubernetes volumes/object stores remain infrastructure authority |
| `frankengraphdb` | Proposed property graph database | Lineage/skill graph storage | No tagged implementation and rider-licensed; reject another authoritative database |
| `frankenjax` | JAX compatibility | Training/research worker only | Rider-blocked; use pinned external Python/GPU jobs |
| `frankenlibc` | glibc interposition/safety membrane | Possible sandbox hardening experiment | Rider-blocked and far below application boundary; reject for initial platform |
| `frankenmermaid` v0.2.0 | Mermaid-compatible diagrams | Report visualization | Rider-blocked and presentation-only; browser-side permissive Mermaid is sufficient if needed |
| `frankenpandas` v0.1.2 | pandas compatibility | Eval result transformations | Rider-blocked; keep pandas inside sandboxed Python jobs, not the Rust service |
| `frankenredis` | Redis compatibility | Optional cache/queue accelerator | Rider-blocked and contradicts PostgreSQL-first minimalism; existing Redis remains optional and non-authoritative |
| `frankenscipy` | SciPy compatibility | Statistical/scientific evaluators | Rider-blocked; use pinned Python scorer images |
| `frankensearch` v1.2.5 | Two-tier BM25/vector hybrid retrieval | Strong conceptual fit for authorized trace, skill, and evidence retrieval | Rider-blocked; integration Beads cannot proceed without written permission/relicensing; pgvector/PostgreSQL remains default |
| `frankensim` | Simulation/optimization/rendering continuum | Possible robotics/world-model research jobs | Rider-blocked and not a control-plane dependency; isolated future research adapter only |
| `frankensim_website` | Product/demo website | None | Do not adopt |
| `frankensqlite` v0.1.17 | SQLite replacement | Local collector cache or CLI state | Rider-blocked; not a server database; use standard SQLite only for endpoint-local spool if needed |
| `frankensqlite_website` | Product website | None | Do not adopt |
| `frankenterm` | WezTerm agent-fleet hypervisor | Development-time swarm observation | Rider-blocked and never a runtime dependency; NTM remains external developer tooling |
| `frankentorch` | PyTorch compatibility | Training/inference workers | Rider-blocked; use official pinned Python/CUDA training images |
| `frankentui` | Terminal UI kernel | Operator/collector CLI UX | Rider-blocked; no dashboard or service value; choose a permissive CLI UI only if a CLI is funded |
| `frankentui_website` | Product website and Beads visualization | None | Do not adopt |

## Adjacent substrate disposition

These are not all Franken-named, but they determine whether a proposed bundle is actually usable.

| Project | Potential role | Decision |
|---|---|---|
| Asupersync v0.3.9 | Structured-concurrency runtime for the Rust control plane | Rider-blocked. Preserve its desired properties as requirements, not code dependencies. |
| `fastapi_rust` v0.3.0 | Rust analytics HTTP API | Direct license is MIT/Apache-2.0, but mandatory Asupersync dependency is rider-blocked and the README calls the framework early development. Do not adopt. |
| `sqlmodel_rust` v0.3.0 | Typed PostgreSQL model/query layer | Rider-blocked. Use SQLx with explicit repository/domain boundaries. |
| Beads Rust / Beads Viewer | Planning and dependency graph | Existing development tooling only; never product runtime or customer data store. Rider prevents bundling. |
| NTM / FrankenTerm | Agent development orchestration | External build/research tooling only; never Helm dependency. |
| CASS / Eidetic / coding-agent-session-search | Local session recall and mining | Useful reference category for endpoint collectors, but rider-blocked. Our collector protocol must remain implementation-independent. |
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

Rejected bundle: `fastapi_rust + Asupersync + sqlmodel_rust`. It is appealing as a coherent developer experience, but two mandatory layers are rider-blocked, the web layer is explicitly early-development, and adopting an entire novel runtime/framework/ORM stack would concentrate correlated failure and maintenance risk.

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

`Frankensearch + Eidetic + FrankenNetworkX` would cover hybrid retrieval, memory, and graph traversal, but all three are rider-blocked and together would create three correlated experimental dependencies. The approved baseline remains PostgreSQL FTS/pgvector plus bounded offline graph computation. A future retrieval sidecar may implement the existing contract only after a benchmark proves PostgreSQL insufficient.

### 3. Evaluator and training plane

`FrankenEngine + FrankenNode + FrankenNumPy/Pandas/SciPy/JAX/Torch` describes an ambitious all-Rust evaluator/training environment. It is the wrong product composition even if relicensed: arbitrary customer evaluators and current ML tooling are Python/CUDA-oriented, and a compatibility stack multiplies conformance risk. Use a small Rust scheduler plus pinned, signed, network-restricted Python/WASM/container runners. The control plane stores specifications, leases, checkpoints, receipts, and results; it does not implement every numerical runtime.

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

This crate adds real value by eliminating repeated, drifting installation probes across Claude Code, Codex, Gemini, and other collectors. It must not enable its FrankenSQLite-backed connector features. Detection is not authorization, proof of ownership, session parsing, continuous watching, or consent; those remain explicit collector responsibilities.

### 5. Document, audio, and report enrichment

`FrankenOCR + FrankenWhisper + FrankenMarkdown + FrankenMermaid` is a plausible enrichment pipeline but not a gateway capability. Each stage has distinct model, privacy, CPU, and artifact requirements, and all are rider-blocked. If customer demand appears, define media-type-specific job adapters and evaluate permissive implementations independently. Never deploy them in inference or analytics API pods.

### 6. Storage and durability replacement stack

`FrankenSQLite + FrankenRedis + FrankenFS + FrankenGraphDB + RaptorQ` is rejected. It would replace mature operational authorities with multiple novel systems, contradict the minimal-service objective, fragment backup/restore and authorization, and add correlated durability risk. PostgreSQL, object storage, Kubernetes volumes, and optional non-authoritative caches remain the platform.

### 7. Operator and developer experience

`FrankenTUI + FrankenTerm + Beads viewers + NTM` can improve development workflows but must stay outside Helm and the customer security boundary. The web dashboard remains the uniform product interface. A future CLI may consume the same public API, but the UI library is selected independently under compatible licensing.

### 8. Snowflake and enterprise data exchange

FrankenSnowflake should not be embedded into the control plane. If a customer requires warehouse export, implement an asynchronous adapter behind the artifact/export protocol with a separate credential, egress, quota, and audit boundary. Prefer standard Snowflake APIs/drivers with compatible support and licensing.

## Permutation rules

The following rules cover meaningful combinations without enumerating useless subsets:

1. Exactly one authority per datum. Derived search, graph, cache, and memory systems never become policy or evidence authority.
2. No experimental dependency on the inference hot path.
3. Separate query serving from index building, and API admission from job execution.
4. Combine libraries inside one binary only when they share scaling, trust, and failure domains. Otherwise compose through a versioned job or HTTP contract.
5. A permissive top-level license does not cure a restricted transitive dependency.
6. Product runtime, optional Helm component, sandboxed job image, endpoint-local tool, CI tool, and research reference are different adoption classes and require different proof.
7. Every optional accelerator must have an authority-preserving fallback and rebuild path.
8. Numerical/media compatibility projects belong in worker images, never the Rust control API.
9. Websites and Beads viewers are not reusable backend architecture.
10. No combination advances from research until the exact stable-tag closure passes the provenance and redistribution gate.

## Recommended decisions by horizon

### Now

- Build the Rust analytics plane on Axum/Tokio/SQLx/PostgreSQL with explicit cancellation and supervision contracts.
- Preserve the Go gateway and one-origin dashboard architecture.
- Keep pgvector/PostgreSQL as the authorized retrieval default.
- Add a license gate before every Franken integration Bead.
- Prototype `franken-agent-detection` default features in the endpoint collector only after dependency/SBOM verification.

### After measured need

- Add an independently implemented retrieval service if the PostgreSQL benchmark fails.
- Add sandboxed Python/WASM evaluator workers and customer-required warehouse/media adapters.
- Add a separate static dashboard deployment without fragmenting browser authentication.

### Only after written permission or compatible relicensing

- Evaluate Frankensearch, Asupersync, Eidetic, FrankenEngine, FrankenNetworkX, or any other rider-licensed project at a pinned stable tag.
- Re-run source, conformance, performance, security, license, and transitive-dependency reviews from scratch. Current metadata is not adoption evidence.

## Sources

- [Dicklesworthstone repositories](https://github.com/Dicklesworthstone?tab=repositories)
- [Frankensearch license](https://github.com/Dicklesworthstone/frankensearch/blob/main/LICENSE)
- [franken-agent-detection v0.1.9](https://github.com/Dicklesworthstone/franken_agent_detection/releases/tag/v0.1.9)
- [fastapi_rust v0.3.0](https://github.com/Dicklesworthstone/fastapi_rust/releases/tag/v0.3.0)
- [Axum v0.8.9](https://github.com/tokio-rs/axum/releases/tag/axum-v0.8.9)
- [Tokio v1.53.0](https://github.com/tokio-rs/tokio/releases/tag/tokio-1.53.0)
- [SQLx repository](https://github.com/transact-rs/sqlx)
