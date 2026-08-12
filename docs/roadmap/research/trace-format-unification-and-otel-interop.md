# Trace-format unification and OTEL interop

Status: beta ingestion decision

## Decision

Use OpenTelemetry as the preferred correlation and transport envelope, not as
the sole source of evaluation semantics.

The ingestion path is:

```text
native producer record + OTLP projection (when available)
  -> source adapter
  -> trace/span/event identity join
  -> canonical trajectory DAG
  -> privacy transform + loss receipt
  -> ClickHouse typed facts and bounded nested-field summaries
```

This is deliberately not a raw-log-to-OTEL conversion. OTLP gives us stable
trace/span IDs, parentage, timestamps, resource attributes, instrumentation
scope, status, and typed attribute values. It does not guarantee that a
producer recorded authorization, tool proposal versus execution, skill
application, retrieval provenance, state change, or terminal outcome. Those
semantics must come from a native producer adapter or remain explicitly
missing.

The OpenTelemetry GenAI conventions now live in their own repository and cover
LLM, agent, embedding, retrieval, and MCP operations. The conventions are the
right vocabulary and correlation layer, but they remain a versioned external
contract that we must record in `source_revision` and `schema_revision`:
[OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai).

## What the local audit found

FrankenGate already has the important lower-level pieces:

- `core/schemas.Trace` and `Span` retain parent IDs, timestamps, status,
  attributes, and timestamped events.
- `plugins/otel` exports resource attributes, instrumentation scope, span
  identity, parentage, status, events, scalar attributes, arrays, and nested
  maps as OTEL `KeyValueList` values.
- `research/trace-intelligence/atif_adapter.py` demonstrates the required
  loss-receipt behavior: projection is allowed to normalize or reconstruct,
  but never silently drop an event.
- `research/trace-intelligence/tracebench.py` explicitly records that tool
  call/result kinds had to be reconstructed when the source was not OTEL. That
  is evidence for preserving native records alongside OTLP, not evidence that
  OTLP can recover missing semantics.
- The self-service eval contract already says to preserve native logs and use
  OpenTelemetry/OpenInference for correlation and explicit trajectory
  projections for replay/eval.

## Producer differences that matter

| Producer | What can be used as authority | Main ingestion risk | Adapter rule |
| --- | --- | --- | --- |
| FrankenGate OTEL plugin | OTLP spans/events plus native `Trace` before export | Content filtering, legacy `gen_ai.*` names, and gateway-specific routing attributes | Prefer native trace facts when available; map legacy and current names into one canonical field with a mapping receipt. |
| Codex CLI | OTLP traces and log events when OTEL is configured; local session/rollout records are a separate native source | Headless and interactive modes may emit different signals; a metric may be absent even when token fields exist on spans/logs | Treat OTLP as an observed projection, retain `instrumentation_scope` and `source_revision`, and mark absent signals rather than backfilling them. |
| Gemini Code Assist / Cloud Code | Google Cloud Logging prompt/response records and metadata logs, when an administrator enables them | It is a Cloud Logging record stream, not automatically an OTLP agent trajectory; logging is configurable and limited to IDE interactions | Implement a Cloud Logging adapter that extracts record IDs, timestamps, project/user policy metadata, prompt/response presence, and any available correlation IDs. Never assume tool/retrieval events exist. |
| Strands Agents + GenAI telemetry | OTLP hierarchy with agent, cycle, model, retriever, and tool spans; optional local `AgentResult.traces` | SDK versions and stability opt-ins change attributes; local traces are not the same schema as OTLP | Prefer OTLP for cross-service joins, use local traces as a native enrichment source, and preserve the SDK/version plus opt-in state. |
| CASS / other local stores | Native event/session records | Local schema and retention policy vary; may have no W3C IDs | Use CASS as the search/index and slice-discovery layer; export or adapt its source records into canonical events, using bounded temporal/session joins only when confidence is recorded. Never invent parentage silently. |

The Cloud Code conclusion is based on Google's current documentation: Gemini
Code Assist logging can contain prompts/responses and metadata, is enabled by
logging settings, and is limited to IDE interactions. See [Configure Gemini
Code Assist logging](https://docs.cloud.google.com/gemini/docs/configure-logging).
Strands' documentation is unusually useful for our target shape: it describes
agent/cycle/model/tool hierarchy, retrievers, tool IDs, tool results, token
usage, and OTLP export. See [Strands traces and OpenTelemetry
integration](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/).
Codex's repository exposes an OTEL subsystem, but the adapter must still treat
the emitted signal set as versioned and mode-dependent: [OpenAI Codex OTEL
source](https://github.com/openai/codex/tree/main/codex-rs/otel).

## CASS-specific notes

CASS is the useful missing piece for coding-agent history. The installed
CASS `0.6.23` reports connectors for Codex, Claude Code, Gemini/Antigravity,
OpenCode, Cursor, Aider, Copilot, Qwen, and other coding-agent sources. Its
local storage normalizes heterogeneous inputs into a searchable conversation
and message layer with source identity, agent, workspace, role, timestamp,
content, extra metadata, token metrics, and tool-call counts. That is exactly
the right place to discover candidate trace slices across a large local corpus.

The CASS export of a Codex session also shows why it is not itself the
Autoeval canonical trajectory. A single export can contain `session_meta`,
`turn_context`, `message`, `function_call`, `function_call_output`,
`custom_tool_call`, `custom_tool_call_output`, and `reasoning` records. It
preserves useful source metadata such as session ID, working directory, model
provider, CLI version, git revision, and branch, but it does not guarantee
OTEL trace/span IDs or distributed parentage. It can also expose encrypted
reasoning fields in an export; those must be excluded before Autoeval
preparation.

Therefore:

- use CASS to search, aggregate, cluster, and select coding-agent sessions;
- use `cass export`/a version-pinned CASS adapter rather than coupling the
  analytics binary to undocumented internal SQLite tables;
- request tool-inclusive exports for trajectory preparation, because search
  intentionally hides tool output by default;
- map CASS `function_call` and `function_call_output` into separate canonical
  proposal/execution/result events only when the source supports that claim;
- map CASS session metadata into source/harness/model/git revisions and
  provenance, not into invented OTEL IDs; and
- reject or abstain on reasoning, missing authorization, missing retrieval
  evidence, and missing terminal outcomes.

CASS should be an upstream discovery and source-adapter dependency for local
coding-agent corpora, not a second analytical engine and not a replacement for
OTLP. Its searchable message index and our ClickHouse fact projection have
different responsibilities.

## Nested fields: preserve, summarize, do not explode blindly

OTLP can carry nested values, but “carried in OTLP” is not the same as
“analytics-ready.” A nested attribute may be a structured tool argument, a
serialized JSON string, an array of messages, an SDK-specific envelope, or a
redacted/omitted value. We need a bounded projection layer.

For each source event, the compiler should produce:

1. **Typed canonical columns** for fields used in joins, grouping, and
   rubrics: trace/span/event IDs, operation kind, model/provider, tool and call
   ID, skill/KB identity, status, timestamps, revisions, and observation state.
2. **Nested field summaries** for every allowed structured attribute: canonical
   JSON path, value type, array/object cardinality, byte length, redaction
   marker, and a digest of the privacy-transformed value. The summary is safe
   for analytics without storing the payload.
3. **A bounded opaque envelope digest** for unrecognized or source-specific
   structure, plus the source path and adapter mapping. This lets us detect
   shape changes without pretending to understand them.

The default limits are depth 8, 256 paths per event, 256 KiB input per field,
and no raw prompt, reasoning, tool argument, tool result, code, or retrieved
document body in ClickHouse. If a value exceeds a limit, record a `missing` or
`truncated` loss item with a digest where allowed. A limit breach must never
become an absent field with no explanation.

Do not turn every nested path into a ClickHouse column. That creates schema
churn and high-cardinality costs. Keep the current typed fact tables and add a
bounded child fact such as:

```text
trace_attribute_facts(
  tenant_id, trace_id, event_id, source_path, canonical_path,
  value_type, element_count, byte_length, value_digest, redaction_status,
  observed_at, schema_revision
)
```

This is an analytical summary, not a payload vault. A future approved artifact
store can retain encrypted case-pack material under a separate policy, but the
beta compiler must remain digest-only.

## Required adapter behavior

Every adapter must emit:

- `source`, `source_revision`, `source_digest`;
- OTEL `trace_id`, `span_id`, `parent_span_id`, resource, scope, and schema
  URL/version when present;
- canonical event kind and mapping status (`observed`, `reconstructed`,
  `inferred`, or `missing`);
- a deterministic parent/ordering decision and its confidence;
- a privacy receipt before hashing or persistence; and
- a loss receipt that accounts for every source record and every dropped,
  normalized, redacted, or unavailable field.

The compiler may join native and OTLP records only when IDs match or the join
is deterministic and recorded. Timestamp proximity alone may enrich a record,
but must not manufacture a tool-result edge or a successful state transition.

For eval, the relevant distinction is:

```text
OTEL envelope       = where/when/who is connected
native adapter      = what the producer claims happened
canonical compiler  = what is safe and comparable across harnesses
rubric              = how task-directed action value is judged
```

## Follow-up test matrix

Before calling the beta portable, run the same canonicalization fixtures
through FrankenGate, Codex CLI, Gemini Code Assist/Cloud Code exports, and
Strands. Verify:

- parentage and event ordering survive retries, branches, joins, delegation,
  and streaming;
- tool proposal, authorization, execution, and result remain distinct;
- skill load/application and KB query/retrieval/citation remain distinct;
- nested maps, arrays, JSON-string attributes, and absent attributes produce
  the same bounded summaries;
- redaction and deletion lineage produce the same eligibility decision; and
- an omitted signal produces abstention/missingness, not an inferred success.

The first implementation task is therefore a bounded `trace_attribute_facts`
projection plus four source fixtures, not a rewrite of the gateway's OTEL
exporter and not a commitment to OTEL-only ingestion.
