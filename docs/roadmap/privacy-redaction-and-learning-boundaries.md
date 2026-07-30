# Privacy, Redaction, and Learning Boundaries

Status: current architecture decision. This document supersedes older roadmap and
mode-output language that treated sanitization or metadata-only capture as the default
for every internal log, trace, eval, retrieval, or learning use.

## Invariant

Frankengate's authorized internal trace plane may retain useful request, response,
tool, and prompt content—including PII—when content logging is enabled by tenant
policy. Individual users may inspect their own histories; authorized team and
enterprise administrators may inspect the scopes granted to them. RLS,
classification, encryption, audit, retention, deletion, and purpose checks protect
that data. Blanket redaction must not make the internal product or incident record
unusable.

For ordinary PII and classified business content, the hard boundary is disclosure, not
mere internal storage. Raw content does not cross to a secondary third-party
observability, evaluation, training, or analytics processor, public/shared dataset,
lower-privilege audience, or unrelated learning purpose merely because it passed
through the gateway. A tenant's explicit selection of a primary inference provider is a
purpose-bound disclosure for that request; it never implicitly authorizes logging,
evaluation, training, connectors, or any other processor. Internal capture, internal
reuse, primary inference, and secondary disclosure are separate policy decisions.
Metadata-only remains the fallback when internal content capture is disabled or a
required control fails.

PII detection is therefore an egress and scope-transition control, not a reason to
erase the authorized internal record. It is also insufficient by itself: sensitive
content includes credentials, source code, unreleased financials, performance and
compensation reviews, HR/legal and health matters, customer or contract data, security
findings, and attributes that a model can infer from otherwise innocuous text.

## Visibility and transformation matrix

| Consumer | Permitted source fidelity | Required gate |
|---|---|---|
| Individual user | Full fidelity for their own governed history | Authenticated subject binding and row scope |
| Team administrator | Full fidelity for granted team scopes | Explicit team-admin grant, RLS, purpose and audit |
| Enterprise administrator | Full fidelity for granted enterprise scopes | Explicit admin grant, auditable override, retention and deletion policy |
| Internal analysis/eval worker | Full fidelity only for its declared same-scope job | Service identity, purpose grant, RLS, bounded output and lineage |
| Internal lower-privilege viewer | Destination-minimized or transformed projection | Field/content entitlement and disclosure receipt |
| Third-party model or processor | Destination-approved transformed copy only | Processor allowlist, secret/DLP policy, exact outbound scan and egress receipt |
| Public/shared artifact | Irreversibly minimized aggregate or reviewed transformed snapshot | Publication review, minimum cohort, rights and re-identification assessment |

PII and credentials are not the same policy class. PII may remain visible to an
authorized internal administrator. Authentication material is never part of the
content plane: strip verified authorization and cookie headers, API and virtual-key
values, bearer/session/OAuth tokens and codes, private keys, reusable credentials, and
secret-manager values before durable capture, indexing, replay, evaluator/model input,
or export. Retain only typed key IDs, fingerprints, and auditable references. A
separately approved credential-forensics vault may preserve a necessary artifact; it is
not a trace, log, embedding, or learning-plane exception.

## Data-path placement

1. Classify request identity, tenant, purpose, route and content policy before capture.
2. Remove verified authentication material before durable capture and again before
   every model, evaluator, index, replay, connector, telemetry, or export boundary.
3. Store full-fidelity internal content only in its authorized tenant/user/team scope,
   with content-logging, retention, classification, encryption, and audit policy
   attached to the row and every derived artifact.
4. Before a scope transition or external disclosure, run streaming-safe secret and
   deterministic recognizers and any policy-required contextual detector.
5. Apply the destination-selected transform: keep internally, drop, redact, mask,
   tokenize/pseudonymize, or encrypt into a restricted vault.
6. Emit a `PrivacyTransformReceipt` for transformed or disclosed copies. The internal
   source remains governed rather than being overwritten by a lossy export copy.
7. Re-scan third-party-bound tool results, retrieved chunks, model input/output,
   evaluator explanations, and candidate skill patches independently. Safe input does
   not imply safe output.

Synchronous inference and internal analysis can use authorized raw content to fulfill
their declared purpose. A detector failure on an external or lower-privilege
destination fails that disclosure closed; it does not silently erase or corrupt the
authorized internal source record.

## Detector ensemble

Run the deterministic credential subset before every durable/content-plane boundary.
Use the broader PII and classified-content cascade only where the destination policy
requires transformation. Its members expose versions and span-level evidence:

- deterministic secret scanners, checksums, structured-field rules, tenant dictionaries
  and exact-data matching for credentials, IDs and known people/accounts;
- Microsoft Presidio analyzer/anonymizer as the pluggable rules/context substrate;
- a locally hosted small encoder such as `Ettin-17M-Nemotron-PII` as a candidate recall
  layer, only after artifact/license, multilingual, latency and calibration review;
- optional larger/local judge for ambiguous high-risk samples, never an external model
  unless egress policy already permits the unredacted content;
- organization recognizers for employee IDs, project codenames, customer/account names,
  repositories, internal URLs, compensation language and regulated vocabularies.

The 17M model is not assumed safe or accurate because it is small. Pin model, tokenizer,
labels and thresholds; measure precision/recall by entity and language on reviewed
enterprise data, adversarial formatting, code, tables, JSON, tool payloads and streaming
chunk boundaries. Compare against Presidio alone and the union/intersection policies.

## Transform semantics

- Irreversible redaction is the default for third-party-bound training, shared
  evaluation and cross-scope skill improvement; it is not the default internal log
  representation.
- Stable pseudonyms use tenant- and purpose-scoped keyed tokens so relationships can be
  evaluated without enabling correlation across tenants or purposes.
- Reversible encryption is reserved for narrowly authorized investigations/replay. Its
  ciphertext may share the authoritative source row and deletion lifecycle for the
  smallest deployment, but it uses a separate versioned envelope/key, is omitted from
  ordinary projections and indexes, and is accessible only through a scoped reveal
  operation with an access receipt. A detached vault is required only when residency,
  key-custody, or lifecycle policy requires it.
- Do not use unsalted hashes for low-entropy identifiers. Salt/key custody and
  referential-integrity scope are explicit; tokens never reveal original length when
  that is sensitive.
- Preserve offsets and typed placeholders sufficiently for tool/schema/trajectory
  tests. The re-identification map is logically separated by envelope, key,
  authorization path, and projection even when its ciphertext shares the source row.

Every `PrivacyTransformReceipt` records detector/rule/model versions, policy and purpose,
entity classes and counts, transformations, confidence bands, source/content hashes,
false-positive override if any, destination eligibility, retention and deletion time.
It contains no discovered secret or raw entity value.

## Friction without surveillance

Friction analytics primarily uses derived events: retry, rephrase, correction,
regenerate, citation behavior, abandonment, escalation, latency, policy refusal, tool
failure and reviewed reason codes. Authorized analysts may drill into governed
same-scope free text when the evidence is needed; a third-party, cross-scope, or
lower-privilege copy is minimized and transformed for that destination. Do not infer
emotion, health, protected class or employee performance for a purpose unrelated to
improving the interaction.

The research distinguishes at least three phenomena:

1. **Accidental friction:** latency, wrong context, repeated work, errors, confusing
   approvals or tool failures. Reduce it and route its evidence to the correct subsystem.
2. **Productive friction:** clarification, evidence review, alternative hypotheses,
   consequential-action approval and uncertainty checks that preserve agency and reduce
   overreliance. Measure decision quality and recovery, not only speed or satisfaction.
3. **Privacy friction:** users censoring, rewriting or avoiding the system because they
   fear disclosure or implicit inference. Provide preview, local transformation,
   explainable policy, correction and deletion controls rather than merely hiding risk.

Perceived ease, trust and confidence are not quality ground truth. Recent work on the
friction-performance and persuasion paradoxes warns that fluent, frictionless output can
increase reliance without improving accuracy. Experiments must pair perceived effort and
satisfaction with verified task outcome, calibrated reliance, error recovery and agency.

## Learning-plane controls

- Internal same-scope evaluation and skill datasets may retain authorized content.
  Third-party-bound or cross-scope datasets contain sanitized immutable snapshots,
  purpose and consent, tenant boundary, detector receipt, provenance, retention and
  deletion lineage.
- Dedupe and clustering may operate on governed same-scope content and vectors. Raw
  content is not copied into a global cross-tenant index; cross-scope features are
  purpose-scoped and policy-transformed.
- Candidate skill changes must pass a privacy diff: new examples, tool parameters,
  generated code and evaluator rationales are rescanned before review and publication.
- Cross-team improvement uses abstracted repair patterns and deterministic rules, not raw
  conversations. Cross-tenant learning is opt-in and requires k-anonymity/minimum cohort
  or an approved privacy mechanism plus legal/security review.
- Data-subject or tenant deletion propagates to raw vault objects, derived datasets,
  indexes, candidates and unpromoted training artifacts. Released model/skill handling is
  governed by a recorded deletion/unlearning policy rather than an impossible promise.
- Privacy detector false positives and misses form a dedicated adjudication dataset, but
  examples are restricted and never become ordinary evaluator prompts.

## Operations and tests

Track content-capture rate, redaction rate, entity precision/recall, raw-egress attempts,
detector failure/fallback, latency and cost, vault access, deletion completion and
privacy-induced task regression. Page on unauthorized raw egress, secret persistence,
cross-tenant token collision or failed deletion; never page with raw content attached.

Conformance includes split entities across stream chunks, Unicode/homoglyphs, base64 and
encoded secrets, nested JSON/tool calls, code/comments, tables, documents/images,
overlapping spans, multilingual names/IDs, prompt injection against the detector,
oversized inputs, detector timeout and failover, pseudonym consistency and tenant
unlinkability.

## Primary references

- Microsoft Presidio: https://github.com/microsoft/presidio
- Presidio text anonymization: https://microsoft.github.io/presidio/text_anonymization/
- Ettin-17M-Nemotron-PII model card: https://huggingface.co/kalyan-ks/ettin-17m-nemotron-pii
- Google, Beyond PII: https://research.google/pubs/beyond-pii-how-users-perceive-and-attempt-to-mitigate-implicit-llm-inference/
- Better AI with Designed Friction: https://journals.sagepub.com/doi/10.3233/FAIA250680
- Friction-Performance Paradox: https://aisel.aisnet.org/pacis2026/adv_theory/adv_theory/3/
- Persuasion Paradox: https://arxiv.org/abs/2604.03237
