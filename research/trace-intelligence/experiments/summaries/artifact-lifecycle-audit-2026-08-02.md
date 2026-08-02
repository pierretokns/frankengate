# Trace artifact lifecycle audit — 2026-08-02

## Question

Can recurrence, frontier semantic review, changed-system replay, and
versioned memory/release state be composed into a safe path from a trace to a
reusable SQL/tool artifact?  The audit deliberately keeps these receipts as
separate cohorts.  They do not share candidate IDs, so a frontier label is
never presented as if it had passed replay.

## Lifecycle result

The eight DataClaw recurrence candidates entered the following deterministic
states:

| state | count | meaning |
|---|---:|---|
| replay pending | 2 | unanimous `reusable_procedure` review, but no candidate-linked replay receipt |
| scope bound | 2 | unanimous `context_specific`; usable only as a scoped review candidate |
| blocked by disagreement | 2 | repeated frontier reviews returned different labels |
| blocked by evidence | 1 | at least one `insufficient_evidence` label |
| blocked by safety | 1 | at least one `unsafe_or_sensitive` label |

**Promotion-ready candidates: 0.**  The definition used was intentionally
strict: unanimous reusable review, authorized semantic replay, changed-system
result verification, and a versioned release record.  No current receipt
provides all four gates for the same candidate.

## Gate evidence

### Recurrence is useful for ranking, not correctness

The frozen Claude-history split found a `+6.3798` percentage-point same-project
lift for exact prior artifacts.  The coarse tool-name/input-key-shape control
was `−6.2541` points.  Exact, scoped identity is therefore a useful candidate
prior; parameter shape is a negative control and must not authorize reuse.

### Frontier review is a queue, not a release mechanism

Five of eight candidates had repeated-review agreement, but two were unsafe or
context-specific and three candidates were either disagreement/evidence
failures.  Even the two unanimous reusable labels remain `replay_pending`.
This supports using a frontier model to prioritize human review and generate a
structured proposal, not to publish a skill automatically.

### Compatibility and replay are the decisive safety gate

In the changed-system fixture, name-only compatibility accepted all five cases
and made two false semantic accepts.  semantic-ID compatibility accepted three
cases with zero false semantic accepts; strict fingerprints accepted only one.

The 100-case stress fixture makes the boundary clearer:

| policy | accepted | semantically correct | unsafe accepts |
|---|---:|---:|---:|
| name-only | 100 | 60 | 40 |
| semantic-ID | 60 | 60 | 0 |

This is strong evidence against name-only artifact transfer and in favor of a
semantic-ID/schema/tool compatibility gate before execution.

### Versioning is necessary but not sufficient

The bitemporal release receipt demonstrates copy-on-write history, rollback,
withdrawal, and the invariant that incomplete extraction cannot promote.  It
does not measure extraction quality, semantic entailment, or user benefit.  A
release ledger can make lifecycle state auditable; it cannot make a bad
candidate correct.

## Architecture decision

The minimal safe composition is:

```text
exact scoped recurrence
  → candidate record with immutable provenance
  → frontier/human semantic review
  → authority + environment/schema compatibility
  → independent replay and result-shape check
  → versioned promotion / rollback / withdrawal
```

The audit rejects three tempting shortcuts:

1. recurrence ⇒ correctness;
2. frontier `reusable_procedure` ⇒ promotion; and
3. matching names or parameter shapes ⇒ safe transfer.

The next decisive experiment is a single consented cohort where the same
candidate ID is carried from trace recurrence through semantic review, changed
system replay, and a prospective next-task outcome.  Until that join exists,
the product boundary is a provenance-aware candidate and review/replay queue,
not automatic memory, skill publication, or cross-user reuse.

## Receipts and verification

- Audit: [`artifact-lifecycle-audit-2026-08-02.json`](../results/artifact-lifecycle-audit-2026-08-02.json)
- Independent verification: [`artifact-lifecycle-audit-verification-2026-08-02.json`](../results/artifact-lifecycle-audit-verification-2026-08-02.json)
- Runner: [`artifact_lifecycle_audit.py`](../../artifact_lifecycle_audit.py)
- Verifier: [`verify_artifact_lifecycle_audit.py`](../../verify_artifact_lifecycle_audit.py)

The audit is content-minimized: only source receipt hashes and aggregate
values are committed; raw prompts, arguments, outputs, and candidate content
remain outside the repository.
