# FrankenSearch assessment

Status: candidate optional retrieval service; not on the inference hot path and not
approved for the launch chart.

## What it provides

The published Rust crate describes a two-tier search pipeline: a fast embedder returns
initial results, then a quality embedder refines them progressively. The documented
stack includes a `potion-128M` fast tier, `MiniLM-L6-v2` (384 dimensions) quality tier,
Tantivy BM25, optional HNSW ANN, FlashRank cross-encoder reranking, and progressive
`Initial`/`Refined`/`RefinementFailed` phases. It also exposes timing/diagnostic metrics
and feature flags for semantic, hybrid, persistent, and durable profiles.

The operational shape is Rust plus `asupersync`, with optional FrankenSQLite-backed
metadata/embedding queues and RaptorQ durability. That is attractive for an optional
retrieval worker or sidecar, but it is not a reason to put a Rust runtime or a model
download into the Go inference process.

## Fit for FrankenGate

**Strong fit:** hybrid lexical+dense retrieval, progressive latency/quality trade-off,
bounded reranking, explicit fast-only mode, and a clear adapter seam. This complements
our finance/jargon benchmark and gives us a concrete p50/p95 comparison against the
current vector-store adapters.

If a prototype is approved, it must use FrankenSearch's canonical
`TwoTierSearcher` and `EmbedderStack` abstractions (including its built-in lexical/
semantic fusion and `Initial`/`Refined`/`RefinementFailed` lifecycle). We must not
duplicate RRF score blending, progressive orchestration, SIMD distance code, or
embedder registries in FrankenGate. Any Rust prototype must also align its
`asupersync` crate source/version with the pinned FrankenSearch revision; a Tokio
bridge is an explicit integration cost, not an excuse to add a second search
runtime to the gateway.

**Open questions:** the published crate docs describe document IDs and search metrics,
but do not establish our required tenant/team ACL-before-retrieval semantics,
deletion/tombstone propagation, encrypted metadata, or multi-tenant cache isolation.
Those must be added at the service boundary and tested before any confidential corpus
is indexed. A progressive result must not expose unauthorized candidates during the
fast phase while the refined phase is pending.

## Vector-level classification contract

Every indexed document and chunk needs an authority-owned metadata envelope, separate
from the embedding payload:

```text
tenant_id, owner/team principals, classification, policy_version,
source_id + source_revision, retention_until, deletion_epoch,
embedding_model + dimensions, index_revision
```

`classification` is an ordered, explicitly configured lattice (for example
`public < internal < confidential < restricted`), not a free-form tag. A caller's
effective principal and clearance must satisfy both the tenant/team ACL and the
classification policy before a candidate is eligible. The predicate must run before
BM25/ANN candidate exposure, reranking, snippets, progressive `Initial`/`Refined`
results, semantic-cache lookup/write, replay export, and telemetry labels. Unknown,
stale, deleted, or policy-version-mismatched metadata fails closed.

Aurora remains the source of truth for the envelope, policy versions, retention, and
deletion epochs. FrankenSearch stores only an authenticated, encrypted derived copy;
outbox events advance tombstones and policy epochs, and an index rebuild is required
when the derived revision is stale. Cache keys must include tenant, principal-policy
version, classification scope, and index revision. Metrics may count filtered
candidates and policy misses but must not emit chunk text or sensitive labels.

This is a security boundary, not merely a ranking feature. The dedicated design and
adversarial test work is tracked in `bif-kyy.17.12.4.1`.

**Model adaptation:** MiniLM-L6-v2 can be treated as a baseline quality embedder. A
domain adapter/LoRA or projection would need an explicit FrankenSearch embedder trait
or a sidecar embedding service; do not patch weights in place. Compare the adapted
model against the frozen MiniLM baseline with FinMTB/FinanceMTEB and enterprise jargon
cohorts, then dual-index/shadow/canary with rollback. The model's upstream license and
weights must be recorded separately from FrankenSearch's license.

## Deployment decision

Do not embed FrankenSearch in the Go gateway binary. Prototype it as an optional
Helm-deployed retrieval service/sidecar with:

- authenticated, tenant-scoped query and ingest APIs;
- ACL filtering before ANN/BM25 candidate exposure, reranking, snippets, and cache;
- source/policy/model/index revisions on every result;
- bounded queues and resource limits so model download or refinement cannot affect
  inference availability;
- durable tombstones and rebuildable indexes;
- OTEL/Prometheus metrics for initial/refined latency, refinement failures, queue depth,
  index revision, and filtered-candidate counts without leaking content;
- fail-closed retrieval for stale policy/index state, while the gateway can continue
  inference without retrieval.

Aurora remains authority for ownership, ACL, retention, deletion and manifests. A
FrankenSearch/FrankenSQLite index is derived and disposable. This preserves the same
authority boundary as the existing vector-store research.

## Required next experiments

1. License and source audit for FrankenSearch, FrankenSQLite, MiniLM-L6-v2, potion-128M,
   Tantivy, HNSW, and FlashRank.
2. Reproduce the published 10K-document latency claims on this machine and record
   hardware, model download state, corpus, and p50/p95 rather than copying headline
   numbers.
3. Add finance/news and enterprise-jargon cohorts, ACL boundary cases, deletion tests,
   and stale-index tests to the benchmark matrix.
4. Prototype a sidecar API and compare fast-only, progressive, hybrid, reranked, and
   adapted modes against the existing Go semantic-cache/vectorstore path.

## Current license and supply-chain boundary

The public project overview and crate documentation establish the architecture, but
they do not by themselves establish a single license for every crate, model, or
runtime asset. Treat the FrankenSearch source license, each Cargo dependency, model
weights, tokenizer, and any cross-encoder as separate inventory entries. The current
decision is therefore **license review pending**, not “MIT by association.” Before a
container or chart ships, require a pinned source revision, complete Cargo license
report, SPDX/NOTICE bundle, model-card license record, checksum-verified model assets,
and an approval for any non-permissive or attribution/share-alike component.

The CASS ecosystem demonstrates that FrankenSearch can support multiple embedders
(including MiniLM, Snowflake Arctic, and Nomic) and an offline model-install path, but
that consumer documentation is not evidence of FrankenSearch's own redistribution
terms or of model fine-tuning rights. Keep model selection and weight distribution
outside the gateway image until those rights and a reproducible benchmark are closed.

## References

- Crate documentation and feature matrix: https://docs.rs/frankensearch/latest/frankensearch/
- Embedder crate: https://docs.rs/frankensearch_embed
- Dicklesworthstone project overview: https://github.com/Dicklesworthstone
- MiniLM-L6-v2 model license: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- FrankenSQLite: https://github.com/Dicklesworthstone/frankensqlite
