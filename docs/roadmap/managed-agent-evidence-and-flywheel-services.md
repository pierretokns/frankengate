# Managed Agent Evidence and Flywheel Services

Status: proposed product boundary
Date: 2026-07-15

## Decision

Build a managed, CASS-inspired evidence plane adjacent to the gateway. Do not embed CASS
or session search in the inference hot path, and do not centralize every user's raw local
agent history by default. Reuse its parser/search/provenance ideas behind our own tenant,
privacy, lifecycle and availability contracts; evaluate exact code reuse only after the
license rider and stable revision are approved in the provenance ledger.

The gateway is uniquely positioned to observe model requests, routing, tool calls,
latency, cost and policy revisions, but it cannot see local edits, terminal results,
tests, user cancellations or whether the task ultimately succeeded. A small local/IDE
collector supplies those endpoint facts after privacy transformation. The managed plane
joins them through opaque trace/session IDs and turns eligible evidence into search,
evaluation and improvement inputs asynchronously.

## Placement and failure isolation

```text
local agent/IDE collectors           gateway trace envelope
          |                                   |
          +---- privacy + eligibility --------+
                              |
                    append-only evidence ingest
                              |
              immutable tenant evidence snapshots
                 /            |             \
          lexical search   derived indexes   offline jobs
                 |            |             |
           user recall    team knowledge   eval/mining/proposals
```

Inference never waits for ingest, indexing, semantic embeddings, feedback aggregation,
CASS-like search, CM-like reflection, graph analysis or proposal generation. Durable
evidence is authoritative; lexical and semantic indexes, aggregates and recommendations
are rebuildable derived state. Backpressure drops or downgrades optional content while
preserving explicit loss/degraded-evidence counters.

## Scope tiers

### Per user: private episodic evidence

- Personal agent/session search and continuation across approved clients.
- Personal feedback, corrections, successful recovery patterns and private draft memory.
- User-controlled retention, export, deletion, visibility and opt-out.
- Tenant/purpose-scoped pseudonyms; no manager-facing individual productivity scoring.
- Default raw history stays local. Upload only explicitly eligible sanitized evidence or
  encrypted user-controlled objects with narrow access.

### Per team/project: curated working knowledge

- Shared resolved incidents, validated workflows, evaluation cases, knowledge gaps and
  approved session excerpts.
- Promotion from personal to team scope is explicit and ACL-checked; it never follows
  automatically from frequency or model recommendation.
- Project/repository/environment revisions and evidence lineage remain attached.
- Team aggregation meets k-anonymity/minimum-support and protected-attribute policies
  where metrics could expose individuals.

### Organization: procedural and governance knowledge

- Approved skills, deterministic tools, rule packs, routing/evaluator policies and
  reusable failure corpora.
- Cross-team statistics are derived, minimized and privacy-budgeted; raw cross-tenant
  search is prohibited.
- Publication requires owner/separation-of-duties approval, replay, critical-slice
  floors, shadow/canary, signed promotion receipt and rollback.

## Flywheel capabilities to evaluate

| Capability | Product placement | Recommendation |
|---|---|---|
| CASS normalization/search | user + team evidence service | Build first; parsers at edge, managed lexical search, optional tenant-local semantic index |
| CASS Memory reflection | user/team/org proposal workers | Build as proposal-only; never write procedural memory automatically |
| Meta Skill/JSM | approved skill marketplace | Already planned; add evidence, outcomes, experiments, provenance and selection learning |
| Beads + BV graph analytics | project improvement graph | Adapt concepts, not gateway runtime; create governed improvement cases and dependency/blast-radius graphs |
| Agent Mail | active multi-agent coordination | Integrate as optional external service/MCP first; do not make inference depend on mailboxes or file leases |
| NTM | developer-side orchestration | Keep client/operator-side; ingest safe outcomes and coordination metadata, never run production orchestration in gateway pods |
| DCG/UBS | deterministic safety/quality evidence | Accept signed findings/receipts; optionally host isolated scan workers, not in request process |
| Brenner/APR/idea-wizard | research and proposal generation | Offline candidate workers whose outputs require evidence and approval |
| RCH/RU/CAAM | workstation/build/account operations | Do not productize in gateway; integrate through approved tools only when a concrete enterprise workflow demands it |
| XF/GIIL and personal-data tools | personal archives/media | Exclude from initial managed plane due privacy and weak gateway relevance |

## Managed CASS differences

The open-source CASS design is local-first: SQLite is authoritative, lexical search is
required, semantic enrichment is optional and derived, model downloads are opt-in, and
corrupt indexes are quarantined rather than silently deleted. Preserve those excellent
properties, but the managed form needs additional contracts:

- tenant, subject, purpose, residency and ACL on every evidence item and index posting;
- object-level encryption and tenant-key crypto-shredding;
- parser sandboxing for hostile or malformed local logs;
- idempotent ingest with source cursor, content digest and deletion tombstones;
- policy-filter-before-index/search, including embeddings and snippets;
- no global embedding/vector corpus or raw query analytics;
- immutable snapshot/index generations with atomic publish and rollback;
- quotas for bytes, documents, embeddings, queries and retention;
- legal hold and deletion behavior that distinguishes content from minimized audit proof;
- explicit exact, transformed, summarized and inferred evidence types;
- compromised collector/device revocation and signed collector manifests;
- zero-trust support bundles and no credentials/tool outputs by default.

## Feedback and learning contract

Capture terminal task result, deterministic tests, user feedback, behavioral friction,
perceived friction and judge output as different observation types. Join gateway attempts
to client outcomes without turning absence of a client event into failure. Record sampling
and missingness. A selection bandit may prioritize which skill/router/prompt/KB candidate
to test, but never authorizes publication or weakens policy.

Candidate generation consumes immutable privacy-eligible snapshots. Evaluation uses
historical failures, representative successes, untouched holdout and adversarial/critical
slices. Promotion is sticky, reversible and audited. Rejection, false positive, rollback,
regression and downstream blast radius feed subsequent proposal selection.

## Launch sequence

1. Define the canonical `AgentEvidenceEnvelope`, content tiers and deletion lineage.
2. Build endpoint collector SDK plus gateway join contract using synthetic data first.
3. Ship per-user private lexical recall with metadata-only gateway traces.
4. Add explicit team curation and validated case promotion.
5. Add offline skill/eval/KB proposal generation and scorecards.
6. Add optional tenant-local semantic search only after leakage and retrieval tests.
7. Add organization-wide derived analytics only after privacy thresholds and labor/
   employee-monitoring review.

Do not begin with a global company conversation index. That is the easiest architecture
to demo and the hardest one to make trustworthy, deletable and socially acceptable.
