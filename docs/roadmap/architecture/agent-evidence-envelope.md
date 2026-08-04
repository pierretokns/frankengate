# ADR: AgentEvidenceEnvelope Schema Contract

Status: Accepted schema contract for managed evidence planning

Date: 2026-07-15

Package: `github.com/maximhq/bifrost/core/evidence`

## Decision

Define `AgentEvidenceEnvelope` version `agent-evidence-envelope/v1` as the canonical,
compact join-and-receipt contract for the managed agent evidence plane. It is not the
authoritative trace-content record.

The contract separates observation facts from policy and privacy authority. Every envelope carries tenant, subject, purpose, residency, ACL, privacy receipt, sampling, missingness, deletion lineage, and immutable revision join keys. Evidence consumers must reject envelopes that lack privacy or authority fields, use unknown enum-like values, contain raw inline content, contain an unsupported content tier, mismatch privacy disposition and content tier, exceed bounded collections, use unsafe free-form strings, duplicate JSON keys, or present an ambiguous observation body.

The schema is intentionally metadata- and receipt-first. It can reference redacted, derived, or vault-controlled artifacts by digest and policy lineage, but it does not embed raw prompts, outputs, tool payloads, terminal logs, user free text, judge rationales, or test transcripts.

## Source Context

The managed evidence roadmap says the gateway observes model requests, routing, tool calls, latency, cost, and policy revisions, while endpoint collectors observe local edits, terminal results, tests, user cancellations, and final task success. It requires terminal task result, deterministic tests, user feedback, behavioral friction, perceived friction, and judge output to be distinct observation types with sampling and missingness recorded.

The privacy roadmap permits full-fidelity PII and classified content inside an
authorized same-scope internal source while excluding credentials everywhere. Every
capture/reuse path still needs purpose, retention, region, subject/tenant policy,
content disposition, authority revision, and deletion lineage. A new destination must
make an independent disclosure decision.

The new `core/evidence` package provides only the schema contract and validation surface. It does not implement ingestion, storage, indexing, redaction, authorization, collector sync, or proposal generation.

## Envelope Structure

Required top-level fields:

- `version`: currently `agent-evidence-envelope/v1`.
- `id`: immutable envelope identifier.
- `observed_at`: timestamp for the observation.
- `producer`: producer kind, producer id, and producer revision.
- `tenant`: tenant id, subject, purpose, residency, and ACL.
- `privacy`: privacy transform receipt.
- `sampling`: sampling inclusion/exclusion decision, rate, and optional seed.
- `missingness`: whether the observation is complete, partial, or absent.
- `deletion`: deletion lineage id, state, subject-delete applicability, and derived artifact ids.
- `revisions`: authority, policy, privacy, and at least one immutable source revision join key.
- `observation`: exactly one typed observation body.

Required authority fields are fail-closed. An envelope without tenant identity, subject identity, purpose, residency, ACL, privacy receipt, sampling decision, missingness status, deletion lineage, authority revision, policy revision, privacy revision, or source revision is invalid. Enum-like fields are allowlisted rather than treated as open strings.

## Observation Types

`gateway_attempt` records provider-attempt facts: request id, attempt id, provider, model, request type, outcome, and fallback slot. It is not the final task result.

`terminal_outcome` records endpoint or CI facts about whether the task/session completed, failed, was abandoned, or remains unknown. It can join to gateway request ids without treating absent endpoint evidence as failure.

`deterministic_test` records test or tool verdicts by run id, suite, case, status, tool revision, and artifact/transcript digests. Digests are allowed; inline logs are not.

`user_report` records explicit user feedback by report id, allowlisted report type, reason code, and optional target observation id. Free-text reports must be transformed elsewhere and referenced only through approved content references.

`behavioral_friction` records derived behavior counters such as retry, regenerate, tool failure, abandonment, or escalation within a window. It is not an employee productivity score.

`perceived_friction` records survey-style perceived ease, trust, confidence, or effort with instrument id, scale, score, and max score. It is not quality ground truth.

`judge_evidence` records evaluator id, rubric revision, pass/fail/inconclusive outcome, normalized scores, and optional explanation digest. Judge rationales are not embedded.

Each envelope must contain exactly one observation body matching `observation.type`.

## Privacy And Content Rules

Allowed `ContentReference` tiers:

- `metadata_only`: no digest or vault URI.
- `redacted`: digest required.
- `derived_digest`: digest required.
- `vault_ref`: digest and vault URI required.

Raw content is not embedded in this compact envelope. A `vault_ref` may resolve to the
authorized full-fidelity internal source only after the caller's current identity,
purpose, tenant/team/user scope, policy epoch, and deletion epoch pass. It must not be
treated as a globally readable sanitized-object pointer. Unknown JSON fields are
rejected by `DecodeStrict`, so fields such as `raw_content`, inline transcripts, prompt
text, tool output, and judge explanations are not silently accepted.

Privacy disposition constrains content tiers:

- `metadata_only`: no content references.
- `redacted`: `redacted` and `derived_digest` references only.
- `derived_only`: `derived_digest` references only.
- `vault_only`: `vault_ref` references only.

The envelope may describe missing or sampled-out evidence through `missingness` and `sampling`; it must not compensate by smuggling raw content into reason fields. Reason-like fields are codes, not arbitrary prose.

## Safe Field Rules

Known string fields use bounded safe formats instead of arbitrary text. Identifiers, revisions, principals, model names, request types, artifact names, and URI-like references are limited to a small ASCII token alphabet and length. Reason codes and score names use a stricter lowercase code alphabet. Digest references must be `sha256:` references. Vault references must use a `vault://` URI form. Slices and maps have explicit maximum sizes.

This is not a semantic secret detector. It is a construction rule for a compact
receipt. Credential stripping occurs before the source enters durable storage or any
model/index path; PII transformation is destination- and scope-specific.

## Revision Join Keys

Every envelope requires:

- `authority`: control-plane authority revision.
- `policy`: authorization/governance policy revision.
- `privacy`: privacy policy/transform revision.
- at least one source-specific immutable revision such as `gateway`, `route`, `collector`, `test_harness`, `judge`, `evaluator`, `skill`, `tool`, or `model_catalog`.

These keys let offline consumers join gateway attempts, endpoint outcomes, deterministic tests, user reports, friction signals, and judge results without relying on mutable process context or current policy state.

## Validation Contract

`AgentEvidenceEnvelope.Validate()` is the public fail-closed validator.

`DecodeStrict([]byte)` rejects duplicate JSON object keys recursively, rejects unknown fields, rejects multiple JSON values, and then validates the envelope. Duplicate-key rejection happens before unmarshalling so a later duplicate cannot silently override an earlier value.

`EncodeCanonical(AgentEvidenceEnvelope)` validates before marshaling. It is canonical only in the schema sense: callers should not treat it as a cryptographic canonicalization format.

The package tests cover:

- valid gateway attempt envelope;
- fail-closed missing privacy and authority fields;
- fail-closed missing tenant, subject, purpose, residency, ACL, sampling, missingness, deletion, policy, privacy, and source revision fields;
- allowlist rejection for enum-like fields;
- every observation type;
- privacy disposition/content-tier consistency;
- bounded safe string, slice, and map validation;
- raw content tier rejection;
- ambiguous observation-body rejection;
- strict decode rejection of duplicate keys, unknown raw-content fields, and trailing JSON values;
- fuzz-seeded duplicate-key, unsafe-field, unknown-enum, raw-field, and decode/encode/decode roundtrip coverage.

## Non-Goals

- No ingestion queue or durable store.
- No evidence indexes, embeddings, search, or proposal workers.
- No redaction detector or privacy transform implementation.
- No gateway hot-path integration.
- No cross-language parser corpus.
- No raw production content capture.

## Consequences

This schema gives downstream evidence work a stable target without pulling learning services into the gateway availability path. It also forces early callers to provide privacy and authority receipts instead of treating evidence as ordinary logs.

The cost is deliberate strictness: early producers may need to emit metadata-only or missingness envelopes until privacy transforms, deletion lineage, and revision manifests are available. That is preferable to accepting ambiguous evidence that cannot be safely indexed, evaluated, deleted, or promoted.
