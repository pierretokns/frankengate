# Privacy, Redaction, and Learning Boundaries

## Invariant

No raw production content enters logs, replay, evaluation, skill improvement, model
training, cross-team analytics, or external observability merely because it passed
through the gateway. Capture and reuse are distinct policy decisions. The default is
metadata-only; content requires an explicit purpose, retention class, region, owner, and
subject/tenant policy.

PII detection is necessary but insufficient. Sensitive content includes credentials,
source code, unreleased financials, performance and compensation reviews, HR/legal and
health matters, customer or contract data, security findings, and attributes that a
model can infer from otherwise innocuous text.

## Data-path placement

1. Classify request identity, tenant, purpose, route and content policy before capture.
2. Run streaming-safe secret and deterministic recognizers before any durable content
   sink or external exporter.
3. Run contextual PII/sensitive-data detection in a bounded local sidecar or worker.
4. Apply the policy-selected transform: drop, redact, mask, tokenize/pseudonymize,
   encrypt into a restricted vault, or keep only under an approved enclave policy.
5. Emit sanitized content plus a `PrivacyTransformReceipt`; raw content is neither a
   fallback log nor an error attachment.
6. Re-scan tool results, retrieved chunks, model output, evaluator explanations and
   candidate skill patches independently. Safe input does not imply safe output.

Synchronous inference can use authorized raw content in memory to fulfill the request,
but learning/observability copies are produced through the privacy boundary. A detector
failure follows tenant policy: metadata-only or fail closed for content capture, never
silent raw capture.

## Detector ensemble

Use a cascade whose members expose versions and span-level evidence:

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

- Irreversible redaction is the default for training, shared evaluation and skill
  improvement.
- Stable pseudonyms use tenant- and purpose-scoped keyed tokens so relationships can be
  evaluated without enabling correlation across tenants or purposes.
- Reversible encryption is reserved for narrowly authorized investigations/replay and
  uses a separate vault, envelope keys, access receipts and deletion lifecycle.
- Do not use unsalted hashes for low-entropy identifiers. Salt/key custody and
  referential-integrity scope are explicit; tokens never reveal original length when
  that is sensitive.
- Preserve offsets and typed placeholders sufficiently for tool/schema/trajectory tests,
  while separating the re-identification map from trace storage.

Every `PrivacyTransformReceipt` records detector/rule/model versions, policy and purpose,
entity classes and counts, transformations, confidence bands, source/content hashes,
false-positive override if any, destination eligibility, retention and deletion time.
It contains no discovered secret or raw entity value.

## Friction without surveillance

Friction analytics primarily uses derived events: retry, rephrase, correction,
regenerate, citation behavior, abandonment, escalation, latency, policy refusal, tool
failure and reviewed reason codes. Free text is separately consented, minimized and
sanitized. Do not infer emotion, health, protected class or employee performance for a
purpose unrelated to improving the interaction.

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

- Training/skill datasets contain sanitized immutable snapshots, purpose and consent,
  tenant boundary, detector receipt, provenance, retention and deletion lineage.
- Dedupe and clustering operate on tenant/purpose-scoped privacy-preserving features;
  raw content is not copied into a global vector index.
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
