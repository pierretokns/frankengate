# OpenTelemetry SDK/Collector E0 round trip

**Status:** completed real SDK → Collector → exporter/storage → reimport

**Run date:** 2026-07-30

## Decision

The narrow operational-topology projection passes its first real transport
gate. Across the twelve governed fixtures, the pinned OpenTelemetry Go SDK,
OTLP/HTTP receiver, Collector batch processor, alpha file exporter, and
Frankengate reimport preserved every projected span identity, parent edge,
link, timestamp, status, canonical low-cardinality attribute, tool-lifecycle
classification, resource attribute, instrumentation scope, and loss-receipt
identity pointer.

This clears issue
[#107](https://github.com/pierretokns/frankengate/issues/107)'s local file
exporter/storage arm. It does not make OTLP a canonical authorization or
evidence store, and it does not establish conformance for a production
backend.

## OpenTelemetry Collector contrib v0.153.0

**Repo:**
[`open-telemetry/opentelemetry-collector-releases`](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.153.0)
v0.153.0, official Darwin arm64 artifact.

The downloaded archive SHA-256 was
`3371b4100c56f853e236b8efa4a134516c5ac09183a07e397a2265f4ab61d63f`;
the extracted binary SHA-256 was
`e7e443f18b50ee12f03aaa1ca3bbd8269007e089abffca7fa387835b44c62afc`.
Both are checked before execution.

## OpenTelemetry Go SDK v1.43.0

**Repo:**
[`open-telemetry/opentelemetry-go`](https://github.com/open-telemetry/opentelemetry-go/releases/tag/v1.43.0)
v1.43.0.

The dedicated module pins the API, trace SDK, and official
`otlptracehttp` exporter to v1.43.0. The exporter sent OTLP protobuf over a
loopback HTTP receiver. The reproducible runner pins the Go toolchain to
`go1.25.0`; the runtime self-reported the same version. No direct JSON POST
was substituted for the SDK.

## Measured corpus

The aggregate fixture matrix contained:

| Measurement | Count |
| --- | ---: |
| Governed fixtures / traces | 12 |
| Canonical events / projected spans | 48 |
| Primary parent edges | 34 |
| Additional relationship links | 16 |
| Tool-lifecycle spans | 8 |
| Authority-event topology spans | 7 |
| Suppressed content fields | 48 |
| Suppressed authority-bearing fields | 30 |
| Projection loss receipts | 12 |

Raw fixture paths, trace IDs, event IDs, content, authority values, the SDK
manifest, Collector output, and process logs were confined to a disposable
directory. Only the aggregate result was retained.

Two independent executions produced byte-identical aggregate JSON with
SHA-256
`9c6d0565227e783b1ef2089842112e0cff7828e95897d33b766ed2d030b18729`.

## Main round-trip result

| Measurement | Retained | Projected |
| --- | ---: | ---: |
| Trace IDs | 12 | 12 |
| Span IDs | 48 | 48 |
| Canonical event identities after reimport | 48 | 48 |
| Parent edges | 34 | 34 |
| Additional links and relationship labels | 16 | 16 |
| Exact start/end timestamps | 48 | 48 |
| Status values | 48 | 48 |
| Canonical low-cardinality attribute sets | 48 | 48 |
| Tool kind + `execute_tool` semantics | 8 | 8 |
| Authority event types, without authority values | 7 | 7 |
| Receipt identity pointers | 48 | 48 |
| Distinct receipt identities | 12 | 12 |

There were zero missing, duplicate, or unexpected span IDs; zero unexpected
links; zero content or authority attribute keys; and zero span-attribute
allowlist violations. Resource attributes and the instrumentation scope also
survived.

The exact timestamp retention is format conformance only. The governed
fixtures lack operational times, so all 48 start/end pairs are deterministic
reconstructions and cannot support latency claims.

## Failure and drop controls

Three negative controls passed:

1. A second real Collector pipeline used the filter processor to drop each
   trace's sequence-zero root. The SDK export still succeeded and storage held
   36 spans. Comparison with the source manifest detected all 12 missing
   spans, and the carried expected event count detected a mismatch in all 12
   traces.
2. Sending through the SDK exporter to an unused loopback endpoint returned a
   nonzero process result. Export failure was not reported as success.
3. Removing canonical event identity from stored OTLP caused reimport to fail.

The drop control exposed an important hard edge: the storage-to-canonical
receipt honestly reported zero silent drops among the **36 spans it received**.
It cannot discover 12 spans discarded before storage. A receipt identity
pointer plus per-trace expected count detects a partial trace, but a wholly
missing trace still requires an out-of-band, content-minimized export manifest.

## Commands

| Task | Command | Notes |
| --- | --- | --- |
| Full pinned reproduction | `cd research/trace-intelligence && make otel-roundtrip` | Downloads/verifies Collector, builds SDK sender, runs main and negative arms |
| Run with an already verified Collector | `FRANKENGATE_OTELCOL_BIN=/path/to/otelcol-contrib ./run-otel-collector-roundtrip.sh` | Binary hash must match the official artifact |
| Build SDK sender only | `cd otel-roundtrip-sdk && GOWORK=off go build ./...` | Uses the dedicated pinned module |
| Run unit/privacy tests | `python3 -m unittest discover -s tests -p 'test_otel_collector_roundtrip.py' -v` | Live test is opt-in |
| Run live integration test | `FRANKENGATE_OTELCOL_BIN=/path/to/otelcol-contrib FRANKENGATE_OTEL_SENDER_BIN=/path/to/sender python3 -m unittest discover -s tests -p 'test_otel_collector_roundtrip.py' -v` | Requires loopback binding |
| Inspect Collector components | `otelcol-contrib components` | Confirms receiver, processor, and exporter availability |

## Config

| Option | Value | Why |
| --- | --- | --- |
| Receiver | OTLP/HTTP on loopback | Exercises official SDK exporter without external exposure |
| Processor | Batch, 100 ms, batch size 512 | One real processor and deterministic flush |
| Main exporter | File, JSON, append false | Disposable OTLP storage and direct reimport boundary |
| Drop processor | Filter `canonical.sequence == 0` | Real Collector-side partial-drop control |
| SDK retry | Disabled | Makes unreachable-exporter failure bounded and observable |
| SDK export timeout | 3 seconds | Prevents a dead endpoint from stalling the arm |
| Span attributes | Exact allowlist | Excludes content and authority values before telemetry |
| Durable output | Aggregate JSON only | Raw and identifier-bearing artifacts remain out of Git |

## Environment variables

| Variable | Purpose |
| --- | --- |
| `FRANKENGATE_OTELCOL_BIN` | Optional path to the exact pinned Collector binary |
| `FRANKENGATE_OTEL_SENDER_BIN` | Enables the opt-in live unittest |
| `FRANKENGATE_OTEL_LISTEN` | Runner-supplied disposable Collector loopback endpoint |
| `FRANKENGATE_OTEL_OUTPUT` | Runner-supplied disposable file-exporter path |
| `GOCACHE` / `GOMODCACHE` | Runner-confined Go build and dependency caches |
| `PYTHONPYCACHEPREFIX` | Keeps bytecode out of the worktree |

## Gotchas

- The Collector
  [file exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.153.0/exporter/fileexporter/README.md)
  is alpha for traces and explicitly does not guarantee stable field names.
  Passing this arm does not choose it as a production store.
- JSON file format writes one OTLP object per line. Reimport must parse every
  line and every resource/scope group, not assume a single document.
- A downstream receipt cannot detect telemetry dropped upstream. Preserve a
  content-minimized export manifest outside the same failure domain.
- A receipt identity hash is a pointer, not the receipt document. Frankengate's
  governed canonical store remains the authority for the full loss audit.
- OTel span links preserve known related-span identity and a Frankengate
  relationship label, but do not turn arbitrary enterprise DAG semantics into
  portable OTel constraints.
- The full contrib distribution is suitable for the experiment but contains
  far more components than Frankengate needs. A production Collector should be
  a minimal pinned distribution after the target backend is selected.

## What Frankengate should build

Keep the architectural split:

```text
governed canonical event DAG + full loss receipts
    |
    +-- content-minimized OTLP projection
          |
          +-- receipt identity + expected event count
          +-- operational IDs, parents, links, timing, status, tool type
          +-- no prompt content or authority values
```

Add a content-minimized export manifest, stored outside the Collector/backend
failure domain, before calling the production export path loss-detecting. Then
repeat this exact arm against the selected production storage/exporter. Test a
whole-trace drop, processor truncation, backend schema evolution, retry
duplication, and restart recovery. Do not expand the telemetry allowlist until
that backend demonstrates equal-or-stronger governance.

## Sources

- Collector release:
  [v0.153.0](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.153.0)
- Collector file exporter source/configuration:
  [v0.153.0 README](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.153.0/exporter/fileexporter/README.md)
- Go SDK and OTLP exporter:
  [v1.43.0 release](https://github.com/open-telemetry/opentelemetry-go/releases/tag/v1.43.0)
- OTLP protocol definitions:
  [`opentelemetry-proto` v1.10.0](https://github.com/open-telemetry/opentelemetry-proto/tree/v1.10.0)
- Frankengate local result:
  [`otel-collector-roundtrip-e0-2026-07-30.json`](../results/otel-collector-roundtrip-e0-2026-07-30.json)
