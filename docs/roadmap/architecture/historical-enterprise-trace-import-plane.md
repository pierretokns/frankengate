# Historical Enterprise Trace Import Plane

Status: required product design; implementation is tracked by
[GitHub issue #109](https://github.com/pierretokns/frankengate/issues/109) and
bead `bif-kyy.17.13.1.1.1`, separately from the research-only corpus loaders.

## Decision

Frankengate needs one governed import plane for historical enterprise traces.
It must not expose a collection of one-off scripts that write directly into log,
trace, vector, or memory tables.

The smallest architecture is:

1. the existing Frankengate control plane creates and authorizes an import job;
2. raw archives remain in the enterprise object store;
3. a bounded worker reads one declared source manifest and runs a versioned
   adapter;
4. PostgreSQL stores the import ledger, canonical trace/event graph, authority
   envelope, loss receipts, quarantine decisions, and deletion lineage;
5. full-text, vector, aggregate, eval, and memory artifacts are derived only
   after promotion.

No new database or continuously running ingestion product is required. Import
workers are ordinary Frankengate jobs, and Aurora/PostgreSQL remains the only
evidence and authorization authority.

## Required import paths

| Path | Accepted source | Preservation target | Important loss or safety rule |
| --- | --- | --- | --- |
| Frankengate/Bifrost backfill | Existing PostgreSQL, ClickHouse, JSONL, or object-store exports of gateway logs and MCP tool logs | Request/session identity, messages, tool lifecycle, provider/model, timing, outcome, route, cost, virtual-key/team/customer provenance | Never infer a person from an API key name; identity mapping must be explicit and versioned |
| OTLP/OpenInference archive | OTLP protobuf/JSON batches, Collector file-exporter output, or content-minimized OpenInference spans | Trace/span identity, parents, links, timestamps, status, events, GenAI attributes, tool lifecycle, resource and scope | A downstream receipt cannot detect a trace dropped before export; require an out-of-band source/export manifest and expected counts |
| ATIF trajectory | Source-pinned ATIF JSONL/JSON | Portable messages, tool definitions/calls/results, metrics, artifacts, and eval assertions | ATIF is a projection, not the enterprise authority; unmapped governance and lineage fields remain explicit losses |
| Native harness history | `~/.claude/projects`, Codex session JSONL/bundles, Pi sessions, cctrace-compatible portable exports, and explicitly supported harness exports | Native ordering, parent graph, branches, subagents, compaction, calls/results, file-history/todo/plan references, model/usage, project and session metadata | Emit an area-by-area completeness receipt. A session or partial-home export is not an entire harness home; credentials, opaque account state, unrelated home files, and unsupported attachments are excluded |
| Canonical Frankengate bundle | Signed manifest plus canonical trace/event JSONL and governed artifact references | Lossless migration between Frankengate environments | Bundle import revalidates tenant, authority, classification, purpose, retention, and deletion state; signatures do not bypass current policy |
| Versioned context and memory | `MEMORY.md`, `CLAUDE.md`, `AGENTS.md`, rules, skills, plans, todos, notebook/document revisions, and supported harness memory exports | Immutable content hash/reference, bitemporal validity, provenance, review state, supersedes/contradicts edges, and sessions that could observe or demonstrably loaded the revision | Current content may not leak backward; file presence is not proof the harness loaded it; generated memory stays a proposal until review |
| Partner/export adapter | Version-pinned Phoenix, Langfuse, Opik, provider, or enterprise data-warehouse export | Only fields covered by an explicit adapter contract and loss receipt | Generic field guessing is prohibited; an unknown schema version is quarantined |

Live OTLP ingestion and historical OTLP archive import share the same canonical
projection contract, but not the same availability path. Historical backfills
must not run through the latency-sensitive inference or live Collector path.

### Harness path allowlists

The expanded public-corpus search found thousands of native files and also
found auth files adjacent to sessions. Import must therefore be
path-allowlisted, never “walk this home directory and ingest everything.”

| Harness | Trace lane | Versioned context/policy lane | Always excluded or separately quarantined |
| --- | --- | --- | --- |
| Claude Code | `$CLAUDE_CONFIG_DIR/projects/**/*.jsonl`; optional prompt-only `history.jsonl` | Explicitly selected plans, tasks/todos, file history, commands, rules, skills, agents, hooks, settings revision, and shell/session-environment snapshots | Credentials, tokens, MCP auth/cache, daemon/account state, paste cache by default, unknown plugin/cache payloads |
| Codex | `$CODEX_HOME/sessions/**/rollout-*.jsonl` and `$CODEX_HOME/archived_sessions/rollout-*.jsonl` | Optional metadata-only `history.jsonl`, `session_index.jsonl`, rules/skills/config revision, and an explicit read-only state-DB adapter | `.codex/auth*`, tokens, caches, account/provider state, `.env*`, shell configuration, and unknown state-DB tables |
| Pi and other harnesses | Version-pinned native session directories with explicit schemas | Explicit configuration/skill snapshots by allowlist | Credentials, provider/account state, caches, and unknown files |

Public search found auth files in nine of the ten largest inspected Codex
repositories. This is an observed failure mode, not a hypothetical one.
Content scanners are a second line of defense; path denial is the first.

Supported transformed/export lanes should include Entire checkpoint branches,
SWE-chat transcript/relational exports, DataClaw `conversations.jsonl`,
share-codex/Pi-Brain exports, cctrace portable bundles, Trace Commons session
trees, and enterprise proxy traces. Every transformed lane must report which
native tool results, topology, compactions, permissions, configuration, and
outcome semantics were removed or synthesized.

## Import lifecycle

```text
register source
  → immutable manifest and source hashes
  → dry-run preflight
  → quarantine or admitted staging
  → identity and authority mapping
  → canonicalize with loss receipts
  → validate counts, graph, lifecycle, and policy
  → atomic chunk promotion
  → asynchronous text/vector/aggregate derivation
  → review, rollback, deletion, or re-import as a new release
```

### 1. Register

The caller submits an object-store URI or uploads through a presigned URL. The
service records:

- tenant and importing principal;
- source kind, producer, schema version, and adapter version;
- immutable object version, byte length, and SHA-256;
- expected file, record, trace, event, and attachment counts when available;
- declared redaction state and source terms;
- requested audience, purpose, classification, retention, and deletion policy;
- identity-mapping release and approval references; and
- whether raw content may be retained, indexed, embedded, exported, evaluated,
  or used for model adaptation.

Public or enterprise data with no declared license is recorded as
`NOASSERTION`. That does not block analysis, but the system must not manufacture
redistribution or training permission.

### 2. Dry-run preflight

Preflight is content-minimized and produces no visible trace rows. It verifies:

- manifest/object hashes and supported schema versions;
- decompression and parser limits;
- source counts and duplicate estimates;
- timestamp ranges and clock anomalies;
- native call/result, parent, branch, link, and session joinability;
- home/export area inventory (sessions, archives, index, history, subagents,
  file history, todos, plans, skills, commands, hooks, settings, caches, and
  unknown areas) with present/absent/intentionally-excluded status;
- possible secret and direct-identifier candidates as aggregate counts only;
- identity-map coverage;
- required authority fields and their mapping policy; and
- expected storage, processing, and derivation cost.

Malformed records, unsupported fields, missing mappings, and count mismatches
are explicit receipts. A dry run never silently drops them.

### 3. Identity and authority mapping

Historical data is not safe merely because it belongs to the same company.
Every promoted trace receives typed columns for:

```text
tenant_id
owner_subject_id or unresolved_subject
audience_mode
optional team_id / project_id / case_id
purpose
classification
retention policy
source policy revision
import authorization epoch
current authorization/deletion epoch
identity mapping release
```

Email, virtual key, API token, username, device, repository, project path, and
provider account are mapping evidence, not interchangeable identities. Mapping
rules are reviewed, versioned, many-to-one aware, and reversible. Ambiguous or
unmapped subjects remain quarantined; they are never promoted into a broad team
or enterprise audience.

Most-restrictive defaults apply when source governance is missing:

- private audience;
- highest configured classification for the import;
- analysis-only purpose;
- no raw export, embedding training, memory publication, or collaboration use;
- current-query authorization required; and
- historical authorization marked unobserved rather than fabricated.

The import epoch proves who authorized the import. It does not pretend to be the
authorization epoch that existed when an old trace was created.

### 4. Canonical staging and receipts

Staging is append-only. Stable identity is derived from:

```text
source manifest ID
object version and SHA-256
source-relative file identity
source record identity or byte offset
adapter name and version
canonical schema version
```

Each source record yields one of:

- a canonical event plus a field-level loss receipt;
- an explicit duplicate reference;
- a quarantined record with a typed reason; or
- a rejected record with a typed, non-content-bearing error.

Adapters may preserve both source lanes when causal joins are absent. They must
not invent call IDs, parents, timestamps, task outcomes, people, teams,
authorization decisions, or learning interventions.

### 5. Validate and promote

Promotion requires:

- source/export count reconciliation;
- zero unexplained record or event loss;
- parent/link/call-result graph checks;
- bounded timestamp and duration checks;
- tenant and subject mapping coverage at the approved threshold;
- fail-closed RLS probes for wrong subject, team, tenant, purpose,
  classification, stale epoch, and deleted source;
- content-retention and secret-handling conformance;
- deduplication and split-leakage receipts; and
- an operator-visible summary of observed, reconstructed, inferred, judged,
  unsupported, and quarantined fields.

Promotion occurs in idempotent, fenced chunks. A retry with the same manifest
and adapter is a no-op after verifying receipts. A changed source, mapping,
adapter, or policy creates a new immutable import release; it never mutates
prior evidence in place.

### 6. Derive after authority

Full-text indexes, JSONB accelerators, embeddings, clusters, summaries, eval
proposals, memory candidates, and enterprise aggregates are downstream
artifacts. They are created only from promoted, currently authorized rows and
inherit the intersection of source authority.

No embedding request, ANN candidate, snippet, count, or cluster membership may
be produced before tenant, subject/audience, purpose, classification,
retention, and deletion assignment.

## Control-plane surface

The non-technical dashboard should expose:

- **Import history**: choose source, upload/register archive, and select a
  reviewed mapping policy;
- **Dry-run report**: counts, date range, formats, identity coverage, tool and
  topology preservation, secret candidates, duplicates, losses, and estimated
  cost;
- **Mappings**: unresolved people, keys, projects, teams, and classification
  decisions;
- **Status**: resumable file/chunk progress without raw cross-user snippets;
- **Quarantine**: typed failures and content access only for separately
  authorized reviewers;
- **Promote / cancel / roll back**: explicit approval with immutable release
  receipts; and
- **Deletion propagation**: source withdrawal progress through canonical rows,
  indexes, aggregates, evals, memories, exports, and model-training releases.

Suggested API operations:

```text
POST   /api/v1/trace-imports
POST   /api/v1/trace-imports/{id}/preflight
PUT    /api/v1/trace-imports/{id}/mappings
POST   /api/v1/trace-imports/{id}/promote
POST   /api/v1/trace-imports/{id}/cancel
POST   /api/v1/trace-imports/{id}/rollback
GET    /api/v1/trace-imports/{id}
GET    /api/v1/trace-imports/{id}/receipts
GET    /api/v1/trace-imports/{id}/quarantine
```

These are control-plane operations, not direct bulk payload endpoints. Large
objects use presigned storage transfer and immutable object versions.

## Minimum PostgreSQL additions

The canonical evidence schema needs:

- `trace_import_source`;
- `trace_import_object`;
- `trace_import_job`;
- `trace_import_checkpoint`;
- `trace_import_identity_mapping_release`;
- `trace_import_identity_mapping`;
- `trace_import_record_receipt`;
- `trace_import_quarantine`;
- `trace_import_release`; and
- `versioned_context_artifact` plus availability, observed-load, citation,
  supersedes, contradiction, and source-evidence edges; and
- dependency edges from import source/object/release to canonical evidence and
  every derived artifact.

Security dimensions remain typed columns. Source-specific metadata and
field-level loss receipts may use JSONB, but JSONB is never authoritative for
tenant, subject, audience, purpose, classification, authorization epoch,
retention, deletion, promotion, or training eligibility.

## Failure modes and required tests

| Failure | Required behavior |
| --- | --- |
| Archive is retried, reordered, or partially duplicated | Idempotent receipts; no duplicate canonical events |
| Worker dies after staging or during promotion | Fenced lease resumes from the committed checkpoint |
| Object changes at the same URI | Hash/version mismatch; stop before parsing |
| Source count omits an entirely missing trace | Out-of-band manifest mismatch; do not promote |
| Unknown schema or tool-result correlation | Quarantine or preserve separate lanes; never guess |
| Email/key maps to multiple people | Quarantine until a reviewed mapping release resolves it |
| Historical authorization epoch is absent | Record it as unobserved; apply restrictive import defaults and current-query authorization |
| Policy or membership changes during import | Stale epoch fences the job; re-authorize before continuing |
| Classification is lowered by the import request | Reject unless an explicitly authorized declassification workflow exists |
| Source is deleted after derived artifacts exist | Transitive invalidation reaches text/vector indexes, clusters, evals, memories, exports, and training releases |
| Reader replica lags policy/deletion state | Protected import review and promotion use a writer/current-enough endpoint or fail closed |
| Secret scanner or content classifier fails | Quarantine content-bearing rows; structural receipts may continue |
| Adapter upgrade changes output | New import release plus diff report; prior release remains immutable |
| Rollback is requested | Create a new withdrawal/rollback release; never erase audit history |

## Delivery slices

1. Canonical bundle and Frankengate/Bifrost log import with dry-run receipts.
2. OTLP/OpenInference archive import using the already validated round-trip
   projection and source-manifest completeness check.
3. Native Claude Code, Codex, and Pi adapters using the empirically measured
   fidelity/loss contracts.
4. Identity/authority mapping UI, quarantine review, and RLS gauntlet.
5. ATIF and selected partner adapters.
6. Derivation backfill, deletion closure, rollback, and disaster-recovery tests.

The first release is successful when one tenant can import a historical archive,
see every and only currently authorized trace in personal history, inspect all
loss/quarantine receipts, rerun the same import idempotently, and delete the
source with verified transitive removal from every derived surface.
