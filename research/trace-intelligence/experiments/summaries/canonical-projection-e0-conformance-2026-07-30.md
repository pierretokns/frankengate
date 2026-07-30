# E0 canonical projection conformance

**Status:** dependency-free ATIF and OpenInference/OpenTelemetry projection arm
complete

**Run date:** 2026-07-30

## Decision

Keep Frankengate's governed canonical event DAG as the evidence authority.

- ATIF v1.7 is a task-trajectory interchange projection for explicitly mapped
  conversation and tool lifecycles.
- OpenInference/OpenTelemetry is a substantially better operational topology
  projection.
- Neither carries the authorization, environment, evaluation, or replay
  semantics needed to replace the canonical store.

Every projection returns a content-addressed loss receipt covering the source
and projected document. A changed source, projection, or receipt fails
verification.

## Source revisions

The arm pins:

- [Harbor ATIF v1.7](https://github.com/harbor-framework/harbor/blob/f5e9d0b71ac4493a4f0620653e2913aee7fc0767/rfcs/0001-trajectory-format.md);
- [OpenInference semantic conventions v0.1.30](https://github.com/Arize-ai/openinference/tree/789d41974c08a9a13147977f28ef4142a07e2106);
- [OpenTelemetry semantic conventions v1.43.0](https://github.com/open-telemetry/semantic-conventions/tree/89aae438b3b3b0a8dd33003c9d70592baf7dbd0d);
- the pre-release [OpenTelemetry GenAI conventions](https://github.com/open-telemetry/semantic-conventions-genai/tree/434c91dcc34ed038e3048c07720ddfed2c6bddfc).

The dedicated GenAI conventions remain pinned to a commit because they do not
yet provide the stable schema contract required for an enterprise evidence
store.

## Fixture matrix

Twelve first-party governed fixtures contain 48 canonical events and 34
parent edges. They exercise:

| Capability | Fixtures containing it |
| --- | ---: |
| General DAG relations | 12 |
| Authorization/classification | 6 |
| Parallel branch/join | 1 |
| Environment state | 1 |
| Evaluation/outcome | 12 |
| Replay/state-transition evidence | 1 |

The result emits only aggregate counts. Fixture content, paths, trace IDs, and
event IDs are absent.

## Measured projection fidelity

| Measurement | ATIF v1.7 | OpenInference/OTel |
| --- | ---: | ---: |
| Projected source events | 48 accounted | 48 spans |
| Canonical event IDs retained after reimport | 0 / 48 | 48 / 48 |
| Canonical parent edges retained after reimport | 0 / 34 | 34 / 34 |
| Reimported events | 12 synthetic placeholders | 48 typed events |
| Silent drops | 0 | 0 |

### ATIF result

The governed fixtures use enterprise-domain event kinds such as authorization
decisions, provider attempts, branch joins, state deltas, deletion lineage,
and derived artifacts. None belong to the existing ATIF adapter's deliberate
portable subset of `conversation.message`, `model.*`, and `tool.*`.

The native adapter therefore:

- manifests and hashes all 48 source events as dropped from ATIF's first-class
  model;
- creates one explicit placeholder step per otherwise-empty trajectory;
- reports 41 additional unsupported graph relations;
- retains zero original event identities or parent edges after reimport.

This is a useful negative result, not permission to coerce every enterprise
event into a chat step. Existing focused tests demonstrate that actual
conversation messages, parallel tool proposals, correlated out-of-order
results, retries, and missing results project correctly. A domain event should
enter ATIF only through a purpose-built semantic mapping whose normalization is
receipted.

The E0 wrapper additionally redacted ten classified or authority-bearing
content fields before ATIF export. ATIF `extra` is not a policy enforcement
boundary.

### OpenInference/OpenTelemetry result

Each canonical event becomes one span with:

- deterministic trace/span identity;
- canonical event ID, sequence, kind, source role, and observation status;
- OpenInference span kind;
- low-cardinality GenAI operation and tool correlation attributes;
- one primary parent and additional known event relations as OTel links.

The sidecar-aware deterministic reimport recovered all 48 event identities and
all 34 parent edges.

That 100% structural result is intentionally narrower than semantic fidelity:

- 75 content, argument, and authority fields were redacted;
- 73 capability fields were normalized into span topology or typed span kinds;
- three authorization/replay fields remained unsupported;
- 96 start/end timestamps were reconstructed because the fixtures contain no
  operational timing.

The reconstructed nanoseconds exist only to make a deterministic span fixture.
They must never be used for latency, ordering, or performance conclusions.

## Loss-receipt contract

For both formats the receipt records:

- source and target format revisions;
- source-event and accounted-event counts;
- zero silent drops;
- source-document and projection hashes;
- exact field paths for DAG, parallelism, authorization, environment,
  evaluation, and replay dispositions;
- normalized, reconstructed, redacted, unsupported, and dropped counts;
- the underlying native ATIF receipt where applicable.

The mutation tests verify that changing the source or projection invalidates
the receipt. Projection and reimport are deterministic, and neither mutates
its input.

## What this means for Frankengate

The all-together system should use:

```text
governed canonical event DAG in PostgreSQL
  ├─ ATIF v1.7 projection for selected portable tasks/evals/training examples
  └─ OpenInference/OTLP projection for operational tracing and span analysis
```

It should not use:

- ATIF as a generic enterprise-event database;
- OTel attributes or baggage as authorization policy;
- span identity retention as evidence that state, reward, or replay is
  preserved;
- a lossy projection as the input to another projection while canonical
  evidence remains available.

For the original enterprise questions, OTLP can support operational failure
localization and trace navigation. ATIF can support selected stored-trace
regression examples. Skill-gap inference, durable memories, procedure
promotion, and cross-user collaboration still require governed canonical
evidence, independent outcomes, review, and prospective measurement.

## Remaining empirical gates

1. Send the OTLP member through a real collector/backend/export round trip and
   measure survival of links, `AnyValue`, resource, scope, and OpenInference
   attributes.
2. Run the ATIF arm over a stratified Wisp conversation/tool sample to measure
   the portable subset separately from the enterprise-event stress corpus.
3. Add the AgentEvals stored-trace assertion projection only after the
   collector round trip passes.
4. Keep raw content and authority references out of telemetry unless the
   collector demonstrably enforces equal-or-stronger governance.

## Reproduction

```bash
python3 research/trace-intelligence/canonical_projection_e0.py \
  --fixtures research/trace-intelligence/fixtures/governed-v1 \
  --output research/trace-intelligence/experiments/results/canonical-projection-e0-conformance-2026-07-30.json
```
