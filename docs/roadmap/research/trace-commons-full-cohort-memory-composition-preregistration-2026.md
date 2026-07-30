# Trace Commons full-cohort memory composition preregistration

**Frozen:** 2026-07-30, before mechanism outcomes were computed
**Status:** preregistered natural-trace mechanics study
**Corpus:** all 28 native Claude Code histories at Trace Commons revision
`112ebd4d03ce852b00e935d523107c3d0c9a65bf`
**Raw-data policy:** temporary local quarantine only; no raw prompt, response,
tool payload, artifact path, or extracted memory content enters Git. The
source-receipt manifest necessarily preserves the public Hub object paths
(whose filenames may contain source session IDs); derived results do not.

The machine-readable protocol is
[`trace-commons-memory-composition-2026.json`](../../../research/trace-intelligence/configs/experiments/trace-commons-memory-composition-2026.json).
It freezes the implementation-sensitive settings summarized here: source
receipt, project join, arm identities, model revision, prompts, schema,
chunking, retry behavior, ranker, reducer, review procedure, and engineering
gates.

## Question

Can one governed PostgreSQL evidence plane compose the useful mechanics from
verbatim memory, latest-only consolidation, bitemporal contextual facts, and
copy-on-write dreaming without losing the native evidence needed to audit or
delete a result?

This study tests representation and lifecycle behavior on volunteered natural
traces. It does **not** test whether a generated memory improves a user's work,
whether an inferred fact is semantically useful, or whether two histories
belong to the same person.

The mechanism arms come from the source-pinned review in
[the memory, skill-learning, and replay matrix](memory-skill-replay-evidence-composition-matrix-2026.md):

1. **Verbatim evidence ledger** — retain each supported observation and retrieve
   the most recent eligible observation as of a query time, following the
   evidence-preserving property taken from MemPalace.
2. **Latest-only consolidation** — keep one mutable value per contextual
   artifact basename without project, environment, or authority in its identity.
   Chronologically newer observations overwrite older ones globally. This is
   the deliberately lossy context-collapsing control.
3. **Contextual bitemporal consolidation** — retain system-time history,
   contextual identity, and interval-censored valid-time changes, following the
   relational subset taken from Graphiti.
4. **Proposal-only dream consolidation** — derive candidate changes into a
   separate copy-on-write proposal set; do not mutate the active release without
   an explicit independent decision, following the safe composition of Dreams
   and LangMem.

## Frozen cohort and classifier

The source cohort is every `sessions/claude_code/*.jsonl` object available at
the pinned dataset revision. Admission is independent of whether a history
contains a memory interaction.

The 28 relative paths, byte lengths, record counts, SHA-256 values, and Hub
ETags are frozen in
[`trace-commons-memory-full-cohort.json`](../../../research/trace-intelligence/configs/datasets/trace-commons-memory-full-cohort.json).

A context-artifact interaction is counted only when a native tool call and its
session-scoped result are joined by tool-use ID and satisfy one of these frozen
rules:

- `Read`, `Write`, `Edit`, or `Grep`: the `file_path` or `path` field, after
  slash normalization and case folding, names `MEMORY.md`, `CLAUDE.md`,
  `AGENTS.md`, or `PROJECT.md`, contains a `/memory/` path component, or contains
  a `/skills/` path component.
- `Bash` or `PowerShell`: the command field contains one of the same normalized
  artifact patterns. Description text and file-content fields are not
  classifiers.

The expected discovery receipt is 28 histories, 14 histories with qualifying
interactions, 67 qualifying calls with 67 matching results, 19 explicit reads,
37 writes or edits, and 11 shell, search, or other operations. A mismatch is a
source-or-classifier failure and blocks the mechanism comparison until
explained. It may not be repaired by changing the classifier after inspecting
mechanism outcomes.

Direct file operations with exact native inputs are eligible for state
reconstruction. Shell and search interactions remain evidence events but are
not promoted into file-state transitions unless their result independently
contains an exact, deterministic state observation. Failed and unjoined
operations never become state.

## Identity, time, and missingness

- Artifact identity is a keyed digest of the normalized, provider-rewritten
  absolute path. No raw path is emitted.
- Project and cohort identity may use a keyed digest of a normalized rewritten
  working directory only. It is not a person identifier.
- Project identity is exact equality of the normalized initial nonempty working
  directory: slash normalization, repeated-slash collapse, case folding only
  for Windows drive paths, and trailing-slash removal. Filename and branch are
  forbidden joins. Same-project histories may overlap and therefore do not
  imply serial continuation.
- Native session IDs, tool-use IDs, and record UUIDs are used for local joins
  and replaced by keyed digests or aggregates in outputs.
- Event order is UTC observation time, then source-file digest, source line, and
  tool-use digest as deterministic tie breakers.
- A changed value observed by a later read establishes only an
  interval-censored change between observations. It does not establish the
  exact valid-time boundary.
- Scrubbed, missing, branched, failed, unmatched, or ambiguous records remain
  explicit counts. The runner may not impute them.

## Evaluation units

The primary evaluation unit is a successful direct `Read` of an admitted
artifact that has at least one earlier eligible observation of the same
contextual artifact. The read is the later observation, not a claim that the
earlier mechanism caused the file contents.

An evaluation cutoff is placed immediately before every qualifying native
operation. Eligible evidence is successful evidence strictly before that
cutoff on the target's native branch **plus chronologically earlier histories
with the exact verified project identity**. The target call/result, its
descendants, and every event at or after the cutoff are forbidden. The retrieval
query is the last user turn plus prior user-visible results on that branch.
Results are stratified by whether the query itself names the target artifact.
A fixed exact-identifier plus PostgreSQL full-text ranker returns at most five
items under a 2,048-token evidence-pack budget; stable event digests break
ties. Dense retrieval is excluded from this representation study.

Two query classes are frozen:

1. **Online as-of query:** what supported state was available immediately
   before the later read?
2. **Retrospective as-of query:** after all observations are ingested, can the
   mechanism reconstruct the supported state that existed at an earlier
   observation boundary?

Exact canonical-content equality is the only content-match success criterion.
Line numbers added by the native `Read` tool and newline/line-ending differences
are canonically removed. Semantic similarity is not used in this study.

For the model-quality phase, latest-only and contextual-bitemporal consolidation
must consume the exact same atomic candidates from one pinned extractor run so
that only the update rule differs. The dream arm uses the same model, seed,
prompt family, input evidence, and token budget but may create multi-event
proposals. Raw extractor outputs remain outside Git; receipts and aggregate
human/model labels are committed. Extraction must be independently reproducible
from the pinned pre-cutoff inputs.

State scoring for the verbatim, latest-only, and bitemporal arms uses one
arm-independent reducer: discard ineligible items; abstain for a known interval
gap or same-boundary conflict; otherwise return the highest-ranked exact state
digest. Dream proposals are not active state and are scored separately.

## Primary outcomes

The runner must emit content-free aggregates for:

- admitted histories, records, native calls/results, qualifying interactions,
  failures, unmatched pairs, branches, and snapshot evidence;
- artifact and project counts plus evaluable online and retrospective queries;
- exact earlier-write-to-later-read matches and interval-censored changes;
- per-arm exact answerability for online and retrospective queries;
- retained evidence revisions, overwritten revisions, unsupported promotions,
  ambiguous transitions, and abstentions;
- contextual collision and negative-control leakage counts;
- proposed dream changes, automatically active dream changes, rejected or
  quarantined proposals, and human-review burden proxies;
- deletion/invalidation closure and stale-authorization-epoch denial in the
  PostgreSQL phase.

Rates must include integer numerators and denominators. Empty denominators are
reported as unavailable, never as zero success.

Co-primary model-quality outcomes are:

1. exact-evidence recall over reconstructable reads: whether returned citations
   intersect the pre-cutoff source events known to support the later observed
   revision; and
2. state-decision accuracy: return the exact supported revision when it is
   proven and abstain when it is unobserved or interval-censored.

Secondary outcomes are valid-citation precision, stale/superseded return rate,
contextual contradictions collapsed, exact later-delta coverage, token and
duplicate-token cost, source-token compression, proposal count, review
accept/edit/reject time, human evidence-support labels (`entailed`,
`contradicted`, `insufficient`), and five-run semantic-hash stability.
Later-transition alignment is never relabeled as correctness.

## Hypotheses and decision rules

**H1 — source fidelity.** The deterministic audit reproduces the frozen
28/14/67 discovery receipt and joins all 67 qualifying results. Failure
invalidates the run.

**H2 — evidence retention.** The verbatim and bitemporal arms retain every
supported revision. Latest-only loses at least one historically answerable
revision if the cohort contains any observed change. If no evaluable change
exists, the comparison is declared uninformative rather than favorable.

**H3 — temporal answerability.** On retrospective queries after a later change,
the bitemporal arm has no lower exact answerability than latest-only and reports
interval uncertainty rather than fabricating a change instant. Superiority is
claimed only with at least five changed-artifact retrospective queries;
otherwise only case counts are reported.

**H4 — safe dreaming.** Proposal-only consolidation causes zero active-memory
mutations without an independent release decision, preserves evidence links for
every proposal, and quarantines failed jobs atomically. Any unsupported or
partially published proposal fails the arm. Candidate usefulness is not an
outcome in this study.

**H5 — governed composition.** Subject, team, classification, purpose, and
authorization epoch are intersected from source evidence. Cross-subject,
cross-team, excessive-classification, wrong-purpose, and stale-epoch negative
controls must all return zero rows. Any leakage blocks adoption regardless of
the other outcomes.

No p-value or confidence interval will be used to turn this convenience cohort
into a population claim. If fewer than five changed-artifact retrospective
queries or fewer than two cross-session exact transitions exist, the
corresponding mechanism contrast is explicitly underpowered.

Comparative model-quality claims stop if fewer than ten reconstructable read
cutoffs or fewer than two independent verified cross-session projects remain.
If fewer than ten independent projects exist, paired counts and exact intervals
are reported without population inference. Contextual bitemporal consolidation
is not justified over latest-only unless it has zero leakage and wrong-context
state, a project-cluster-bootstrap 95% lower bound of at least -0.05 for its
evidence-recall difference, and a positive project-cluster-bootstrap 95% lower
bound for its state-accuracy difference. Dream proposals may be unsupported but
must then be rejected or quarantined; unsupported **active promotions** have
zero tolerance. A release policy remains disabled unless the Wilson 95% lower
bound for independently human-supported accepted proposals exceeds 0.90, and
even that threshold does not authorize automatic promotion. These are
corpus-only engineering gates, not population inference. The verbatim arm
remains the product fallback if consolidation cannot improve state accuracy
without losing recall.

Human review is a census of all dream proposals and reconstructable read
cutoffs. Two reviewers, blinded to arm and the later natural action, receive
items in order randomized with seed `20260730`. They label `entailed`,
`contradicted`, or `insufficient` using the frozen all-material-parts rubric;
a third blinded reviewer adjudicates disagreement. Review time is measured from
item open to label submission. Only keyed reviewer digests and aggregates are
durable.

## PostgreSQL phase

The same admitted transition receipts will be loaded into disposable
PostgreSQL tables with typed authority and temporal columns. JSONB may retain
sparse native evidence metadata, but authority, artifact identity, event time,
system time, valid-time bounds, release membership, and evidence edges remain
typed columns.

The database phase must:

- use native RLS for tenant, subject/team audience, classification, purpose,
  and current authorization epoch;
- give importer, proposer, reviewer/releaser, runtime, and auditor the minimum
  separate capabilities needed by the experiment;
- make evidence and releases append-only, with withdrawal/invalidation rather
  than mutation;
- run in a transaction and leave no study rows after rollback; and
- emit server/extension versions and assertion aggregates, not trace content.

This phase tests PostgreSQL semantics applicable to Aurora PostgreSQL. It is not
evidence that an unverified extension is available on Aurora or that Aurora
operational limits have been benchmarked.

## Falsification and claim boundary

The study is falsified or narrowed when:

- source bytes do not match the pinned receipt;
- the frozen classifier does not reproduce its discovery counts;
- native joins, time ordering, or edit reconstruction are ambiguous and the
  runner silently promotes them;
- any committed result or aggregate emits content, reversible paths, or raw
  identifiers (authorized temporary quarantine outputs are permitted);
- latest-only and bitemporal are compared without changed retrospective cases;
- a proposal is described as a fact, a release, or a useful memory without
  separate evidence; or
- an authority negative control returns any protected row.

A deliberately future-contaminated positive control must be detected as
leakage, and a same-basename/different-project placebo must never be retrieved.
Trace-embedded instructions are evidence text, never analyzer instructions.
Human reviewers label support from pre-cutoff evidence before seeing the later
natural action; model support judgments stay separate. Forks, snapshots, and
transformed duplicates are deduplicated before scoring, and influenced events
cannot independently validate the memory that influenced them.

A passing result supports only this statement: Frankengate can represent and
govern the observed natural artifact transitions with the measured retention,
temporal, proposal, and isolation properties. A later preregistered replay or
online experiment is required to claim better answers, fewer repeated
frictions, better skills, or improved enterprise work.

## Post-run independent-audit amendment

**Added before publication, after the first deterministic execution.** The
initial implementation was independently audited and its first aggregate was
discarded. The audit found that repeated observations were being described as
revisions, overlapping sessions were eligible as if serial, the historical
query included its own later read without saying so, and two negative-control
zeros were structural constants rather than executed controls.

The corrected preflight therefore applies these stricter rules:

- a revision is deduplicated by contextual artifact plus exact content digest;
  repeated identical reads are source observations, not overwritten revisions;
- cross-session contextual evidence is eligible only when exact normalized
  project identity matches and the complete native session time ranges do not
  overlap;
- the exact transition count requires different source and target sessions;
- the historical metric is named **post-observation retention**, because the
  target read is an evidence observation after ingestion. It is not independent
  answerability and cannot support H3;
- changed post-observation cases require a same-branch continuation or a
  verified serial-session relation;
- the same-basename/different-project placebo, future-contaminated positive
  control, and future filter report case denominators and executed outcomes;
  absence of cases is `not_run`, never a fabricated zero; and
- the runner verifies and receipts the machine-readable experiment
  configuration. The PostgreSQL ranker, model, and human phases remain
  explicitly `not_run`, so the artifact is a deterministic mechanics preflight,
  not the complete multi-phase arm evaluation.

These changes narrow claims and remove post-observation ambiguity; they do not
rescue any hypothesis. The discarded first aggregate is not retained as
evidence. The corrected result remains underpowered for H3 and for any
comparative model-quality claim.

A second independent audit of version 2 found additional reporting and
contract defects before publication, so that aggregate was also discarded.
Version 3:

- reports the same-basename placebo per arm: contextual-bitemporal passes,
  while context-collapsing latest-only fails and is not presented as safe;
- applies the frozen common reducer and records interval-gap semantics
  explicitly;
- distinguishes 50 source observations from 48 unique revisions;
- uses manifest receipt order for equal-time source tie-breaking;
- validates every deterministic configuration section used by this phase;
- makes all empty negative-control populations `not_run` and all observed
  leaks `failed`, with control status included in the decision receipt; and
- marks failed-job atomicity `not_run` instead of simulating quarantine with
  constant counts.

These corrections further narrow H4 to inactive-proposal mechanics only. They
also establish that the latest-only arm fails contextual isolation on this
cohort; they do not authorize a quality or enterprise claim.

A third audit found that version 3's two online abstentions were selected with
the target `Read` result: the interval gap was knowable only after the query
cutoff. That aggregate was discarded as future-contaminated. Version 4 permits
interval-gap abstention only from an open-gap marker observed strictly before
the query. This cohort contains none, so the honest online result is one exact
and two stale returns. Target content is used only afterward to score the
pre-cutoff selection. This correction does not change the 48-revision retention
or 3/6 latest-only context-leak findings.
