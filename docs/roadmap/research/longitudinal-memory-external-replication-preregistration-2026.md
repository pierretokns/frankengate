# Longitudinal memory external replication and pre-model protocol

**Frozen:** 2026-07-30, after deterministic source screening and before any
model output or human label

**Status:** post-discovery external mechanics replication; prospective model
and blinded-review preregistration

**Claim boundary:** the deterministic source counts are exploratory because
Fable-5 was selected after its context-transition counts were inspected. The
model prompts, evidence boundaries, output schemas, review procedure, failure
rules, and decision gates are frozen before those later phases. No part of this
document turns the source screen into a confirmatory population study.

The machine-readable protocol is
[`longitudinal-memory-model-human-replication-2026.json`](../../../research/trace-intelligence/configs/experiments/longitudinal-memory-model-human-replication-2026.json).

## Why the cohort changed

The original full-cohort Trace Commons study had only three reconstructable
read cutoffs, one changed-state case, and one exact cross-session
write-to-read transition. It correctly stopped as underpowered. A separate
source screen found that the pinned
[Glint Fable-5 raw Claude archive](https://huggingface.co/datasets/Glint-Research/Fable-5-traces/tree/e05c417852fc59fd8da758e68b352732423ca0cb/claude/projects)
contains 79 top-level histories and 36 nested subagent histories. The primary
cohort admits the 79 top-level files only; top-level placement is not treated
as proof of human authorship.

The Fable stratum contributes 14 reconstructable reads, nine changed-state
cases, and four exact serial cross-session transitions. Those four transitions
span two exact project contexts, four session pairs, and two context artifacts.
Together with the independently pinned
[Trace Commons revision](https://huggingface.co/datasets/trace-commons/agent-traces/tree/112ebd4d03ce852b00e935d523107c3d0c9a65bf),
the source-stratified totals are 17 reads, ten changed cases, and five exact
cross-session transitions over three exact-transition project contexts.

These counts clear the earlier `10 / 5 / 2` mechanics gate. They do not clear a
new confirmatory diversity gate of at least three source families and five
project contexts contributing exact transitions. Current evidence is two
source families and three source-scoped project contexts. Model and review
work may therefore proceed as an exploratory within-corpus replication;
architecture-quality, employee, enterprise-transfer, and population claims
remain blocked.

## Privacy-boundary amendment

Before any model output or human label was observed, the execution boundary was
clarified: useful internal logs are not blanket-redacted. Authorized local
models and administrators may use the governed internal source under its
existing RLS, classification, audit, retention, and deletion controls. Raw
content may not be sent to a third-party model. The frozen OpenAI arm therefore
remains blocked until a separate external-egress gate passes, while a local
model arm may proceed and must be reported separately. An export transform
creates a derived copy and never overwrites the internal trace.

The first one-unit local mechanics smoke was deliberately non-confirmatory. It
revealed two protocol defects before the full run: the longitudinal protocol
had failed to carry forward the already-frozen 2,048-token/five-candidate
evidence budget, and the local Qwen runtime omitted an explicit `null`
`evidence_ref` from otherwise valid abstentions. The full local run therefore
uses the pre-existing whole-item/trailing-item truncation rule and a narrowly
reported serialization adapter for omitted-null abstentions. A second bounded
smoke showed that plain-text JSON was still incomplete, so the local adapter
uses the snapshot's already-pinned native function-calling path to submit the
same three decision fields. No semantic smoke outcome was used to select an arm
or metric; the amended local run remains post-pilot exploratory rather than
confirmatory.

## Source independence and privacy

The selected Glint raw archive and
[cfahlgren1/Fable-5-traces at `0ba6f538…`](https://huggingface.co/datasets/cfahlgren1/Fable-5-traces/tree/0ba6f53852f296f8389290b112054b47cec2dc1f)
are a 115-of-115 byte-exact mirror. They are one source-family/publisher-home
cluster, never two independent datasets. Direct duplicate controls between
the admitted Fable and Trace Commons strata find zero exact file hashes,
native session IDs, record UUIDs, session-scoped tool IDs, or content-free
session-shape signatures. Those controls do not establish distinct people or
rule out semantic or upstream-family overlap.

The [Fable dataset card](https://huggingface.co/datasets/Glint-Research/Fable-5-traces)
labels the corpus machine-generated/synthetic, describes it as
distillation-oriented, warns that raw telemetry is unsanitized, and provides
no explicit per-user donation, consent, or redaction protocol. The raw archive
therefore stays in the authorized local research boundary. It may be inspected
by authorized researchers and local models, but it is not approved for
training, quotation, or direct third-party-model egress.

This gate applies only before a third-party model call or a lower-privilege
export. It does not redact the internal source, the authorized administrator
view, or a fully local analysis run. Before such an external call, an
aggregate-only scanner must:

1. replace configured credential and bearer patterns with typed placeholders;
2. replace high-entropy secret candidates without emitting their values;
3. preserve within-pack exact-identifier equivalence through stable local
   placeholders;
4. rescan the final evidence pack and fail closed on any remaining candidate;
5. commit only counts, class labels, and receipts; and
6. keep the unsanitized evidence pack in an authorized local quarantine.

If that gate cannot be proved, the phase remains local-model-only or blocked.
Public availability is not treated as permission to relay possible credentials
to another processor.

## Frozen evaluation units

The primary population is the census of all 17 successful native reads with at
least one eligible earlier observation under the existing branch and strictly
serial same-project rules. Source identities and project identities remain
stratified; no user identity is joined or inferred across datasets.

Each cutoff is immediately before the target read. Inputs may include only:

- successful evidence earlier on the target branch;
- evidence from a strictly earlier non-overlapping history with the exact
  normalized project identity;
- authority-compatible evidence for the same source stratum; and
- the target query material available before the call.

The target call, target result, descendants, overlapping histories, and all
future events are evaluator-only. The later read result scores a selection
afterward; it may never select evidence or cause an abstention.

## Arms and questions

Five arms use the same cutoffs:

1. **No memory** receives the target query without prior memory evidence. It is
   a sanity control, not a competitive product design.
2. **Verbatim** receives the eligible evidence ledger.
3. **Latest-only** receives one globally latest basename candidate with no
   project context. It is the deliberately lossy control.
4. **Contextual bitemporal** receives the eligible contextual revision history
   as of the cutoff.
5. **Proposal-only dream** receives the same eligible evidence as the
   contextual arm but may produce only reviewable, inactive candidates.

The state task returns either one supplied `evidence_ref` or an abstention with
a closed reason enum. The model never emits or guesses a state digest. The
evaluator resolves a selected reference to its quarantined content digest and
compares it with the later observed digest.

The candidate task extracts atomic facts, preferences, procedures, frictions,
questions, or relations. Every candidate must preserve source/project/time
context, cite supplied evidence, and be labeled `entailed`, `contradicted`, or
`insufficient`. Dream output is a proposal, not active memory.

## Outcomes and review

Primary outcomes are exact state-decision accuracy, exact-evidence recall,
correct abstention, stale/wrong-context return rate, and valid-citation
precision. Secondary outcomes include five-run semantic-hash stability, token
cost, latency, monetary cost, proposal count, review time, and blinded support
labels.

Two human reviewers, blinded to arm and later target content, label every model
candidate and state decision. A third reviewer adjudicates disagreements.
Model judges may be recorded separately but never counted as human review.
Only keyed reviewer receipts and aggregate labels may be committed.

Results are paired by cutoff and reported by source family and source-scoped
project cluster. With only a few effective clusters, the analysis is
descriptive. It will not manufacture population p-values, confidence claims,
or enterprise generalization.

## Stop and release rules

The run stops or remains sealed if:

- a source or screening receipt no longer matches;
- the egress sanitizer fails, changes after seeing model results, or emits a
  candidate value;
- an evidence pack contains target or future material;
- structured output validation fails after the frozen retry schedule;
- a model-selected reference was not supplied to that arm;
- raw text, paths, identifiers, model output, or review items enter Git; or
- any unsupported proposal becomes active.

Passing within-corpus model or review metrics does not authorize automatic
promotion. Promotion always requires a separate authorized release decision,
and withdrawal or deletion must invalidate both retrieval and downstream
influence.
