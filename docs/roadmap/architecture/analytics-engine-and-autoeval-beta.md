# Analytics engine and Autoeval beta architecture

Status: proposed decision

## Decision

Keep analytics as an add-on service, not a module embedded in the FrankenGate
inference binary. Make `analytics-go` the separately deployed analytics and
evaluation binary. Keep `analytics-rs` as migration reference code only. Add
Go adapters and workers where they touch the gateway, existing logstore,
OpenTelemetry, and ClickHouse.

The boundary matters more than the language:

- the gateway remains responsible for serving inference with predictable
  availability and latency;
- the analytics control plane owns jobs, leases, experiments, runs,
  evaluations, artifact manifests, tenant fencing, and deletion lineage;
- trace preparation and candidate execution are asynchronous workers; and
- query engines are analytical projections, never the authority for mutable
  lifecycle state or authorization.

The Go binary is in this repository because it shares the canonical trajectory,
privacy/evidence, ClickHouse, and rubric contracts. Its deployment boundary is
separate because evaluation ingestion, judge work, and analytical queries must
not affect inference availability. The Rust directory is historical reference
code only: it was never a production dependency, so there is no live cutover or
dual-run requirement.

## Choose ClickHouse

| Concern | Choice | Reason |
| --- | --- | --- |
| Jobs, leases, experiment/run/evaluation lineage, tenant RLS | PostgreSQL via the `analytics-go` parity target | transactional authority and lifecycle semantics; Rust remains the migration source |
| Shared and beta event facts, high-cardinality slices, retention, dashboards | ClickHouse | one append-oriented analytical store for wide trace/event facts |
| Large redacted payloads and case packs | approved object store/filesystem | digest-addressed artifacts, not hot rows |

ClickHouse is the production projection, not a replacement for PostgreSQL.
FrankenGate already has a Go ClickHouse logstore and ClickHouse Go client
dependencies, so a trace-fact adapter can reuse existing connection,
migration, retention, and test conventions. The adapter must be append-first:
corrections are new versions with lineage, not mutable control-plane updates.

ClickHouse is the only analytical query engine. It is used in the beta as a
single-node/container add-on and later can scale for several tenants,
continuous ingestion, longer retention, concurrent dashboards, or cross-run
aggregation. Its official Go integration supports native/HTTP connections,
batch inserts, and queries; that matches the existing Go integration surface.
See [Integrating ClickHouse with Go](https://clickhouse.com/integrations/go)
and [ClickHouse's OpenTelemetry overview](https://clickhouse.com/resources/engineering/opentelemetry-otel).

Parquet remains a portable export/interchange format and artifact for offline
transfer; it is not a second supported query path. The beta must run against
the same ClickHouse schema and report code as production. This avoids two SQL
dialects, two planner behaviors, two performance profiles, and report drift.

## Data planes

```text
gateway / OTel / authorized exports
  -> Go source adapters
  -> canonical trajectory DAG + loss/privacy receipts
  -> immutable Autoeval case pack (Parquet export + manifest)
  -> ClickHouse fact projection and Autoeval reports

analytics-go control plane/workers
  -> ClickHouse facts and evaluation reports

legacy analytics-rs control plane (PostgreSQL, migration source)
  -> job/run/evaluation/artifact lineage
  -> leases, retries, tenant fencing, deletion propagation
```

The ClickHouse fact model should contain bounded, sanitized facts rather than
raw prompts or unrestricted tool results. Initial tables should be conceptually
split into:

- `trace_runs`: one row per trace/run/revision, with tenant, dataset, harness,
  model, skill, knowledge-base, and source revisions;
- `trace_events`: one row per canonical event, with parent edge, sequence,
  event kind, observation status, tool/skill/KB identifiers, argument/result
  digests, and bounded metrics;
- `autoeval_cases`: one row per checkpoint/view, with case-pack and transform
  digests, eligibility, missingness, contamination, and split membership; and
- `autoeval_scores`: one row per candidate/evaluator/rubric revision, with
  score, confidence, abstention, evidence IDs, and lineage.

Every projection row must carry `schema_revision`, `source_revision`,
`privacy_receipt_id`, `loss_receipt_id`, `case_pack_digest`, and a deletion
lineage key. No evaluator may query raw observability tables directly.

## Complex traces and portability

The Autoeval claim is only portable when semantics survive a harness/model
change. A format conversion is insufficient. The canonical DAG must preserve
these event families where present:

- model request/response and turn boundaries;
- tool proposal, authorization, start, completion, failure, and result;
- skill lookup, load, application, and version;
- knowledge-base query, retrieved item/citation, snapshot, and freshness;
- retries, fallbacks, branches, joins, delegation, and cancellation; and
- observed state deltas and terminal outcomes.

Each event records its source, parent edge, observation status, content/digest
policy, and relevant model/harness/tool/skill/KB revisions. If a harness cannot
provide a field, the adapter emits `missing` plus a loss receipt and the case
may abstain. It must never infer a tool result, state change, or success.

Every case pack must include a support matrix covering:

```text
action semantics       observed | reconstructed | missing
tool/skill/KB context  observed | reconstructed | missing
terminal outcome       observed | missing
privacy/deletion       valid    | invalid
future contamination   none     | detected
```

The reproducibility test matrix is:

1. same harness, model swap;
2. same model, harness swap;
3. same task, skill enabled/disabled/version-swapped;
4. same task, knowledge-base snapshot/freshness swap;
5. protocol-equivalent tool calls represented by different harnesses;
6. leave-one-harness-out and leave-one-model-family-out evaluation; and
7. temporal and task-family holdouts with a randomly audited executed subset.

For each slice, compare neutral-prefix candidate rankings to independently
executed next-action outcomes. Report action-value rank correlation, top-k
selection agreement, calibration error, outcome regret, abstention/coverage,
contamination rate, and evaluator cost. Report slices separately; a pooled
average cannot establish portability.

The claim is supported only when the relationship survives the prescribed
model/harness/skill/KB changes, the executed reference subset, known bad-action
mutants, and leakage audits. Otherwise the report must say which semantic
dimension is unsupported and abstain from generalization.

## Corporate beta

The beta should be a local-first CLI and optional worker service:

```text
tracecase prepare  --manifest cohort.json --output case-pack/
tracecase validate --pack case-pack/
tracecase score    --pack case-pack --candidate candidate.jsonl --rubric rubric.json
tracecase report   --pack case-pack --clickhouse http://localhost:8123
```

The beta accepts authorized canonical, CASS-export, ATIF, OTLP, and fixture
inputs through adapters. CASS search results remain discovery only; complete
source retrieval and digest verification are required. Candidate runners have
no live-tool capability. Corporate data stays local unless a customer
explicitly configures an approved ClickHouse endpoint. A single-node ClickHouse
container is the supported local deployment.

Beta promotion gates:

- zero raw-data egress in a privacy-canary run;
- deterministic case-pack and report digests;
- no future/outcome/private-reasoning leakage;
- deletion and tenant isolation tests pass;
- known-good, no-op, random, and known-bad mutants separate as expected;
- executed-reference agreement is reported with confidence intervals;
- model/harness/skill/KB portability slices meet their declared support floor;
- judge calibration and abstention meet the rubric's thresholds; and
- cost, latency, and storage budgets are measured on a representative cohort.

The beta report is a retrospective estimate of action value. It is not a
causal claim about an external world and cannot automatically promote a live
route, model, prompt, skill, memory, or policy.

## Delivery order

1. Freeze the canonical event and `autoeval-case-v1` contracts.
2. Implement the single-node ClickHouse report path and conformance fixtures.
3. Add the cross-harness/model/skill/KB invariance matrix and executed reference
   runner.
4. Add the rubric authoring/calibration pack.
5. Add the Go ClickHouse fact projection and run the beta against the production
   schema.
6. Publish a gated corporate beta with a clear abstention report.

This order keeps infrastructure from hiding a weak evaluation claim: first
prove the case and rubric contracts, then scale the analytical projection.
