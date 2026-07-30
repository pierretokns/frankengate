# Frankengate enterprise trace-intelligence transfer study

**Status:** preregistration-ready study design
**Date:** 2026-07-30
**Scope:** the smallest academically defensible program that connects public
benchmark traces and consented real-user traces to Frankengate's original
enterprise questions
**Depends on:** the
[all-together architecture](./trace-intelligence-all-together-system-and-experiment-ladder.md),
[public corpus inventory](./public-agent-trace-dataset-inventory.md), and
[MATM paired-memory pilot](../../../research/trace-intelligence/experiments/summaries/matm-alfworld-paired-pilot-2026-07-30.md)

## Decision

Do not evaluate public traces “as if they were the enterprise.” Use them to qualify
mechanisms, then require a separate governed prospective study for claims about
enterprise users, teams, capability support, collaboration, memory utility, or model
improvement.

The smallest defensible study has three evidence tiers:

1. **mechanism qualification:** licensed public benchmark traces with known task and
   outcome structure;
2. **ecological stress test:** explicitly donated real-user harness histories,
   quarantined and minimized before analysis; and
3. **enterprise transfer:** consented Frankengate traces with current authorization,
   independently observed outcomes, user correction, and randomized or otherwise
   identifiable interventions.

The tiers answer different questions. A result must not inherit a stronger claim merely
because all three use the same canonical event DAG and analyzers.

```text
public benchmark evidence
  -> format, retrieval, diagnosis, eval, replay, and memory-mechanism validity

donated real-user evidence
  -> importer robustness, organic-friction coverage, exact-identifier behavior,
     proposal feasibility, and failure discovery

consented enterprise evidence
  -> personal usefulness, durable benefit, capability-support validity,
     collaboration utility, memory utility, and intervention causality
```

The current MATM result is the design warning: changing the nominal retrieval-depth
condition produced no reliable aggregate success difference, and the released rows
omit the retrieved items and prompt injection. “A trace was retrieved” is not evidence
that its content helped, was used, or should become memory. Every enterprise treatment
must therefore record exact artifact exposure, view/use/edit behavior, and an
independently measured outcome.

## What “real-user traces” may contribute

A public repository containing a genuine `~/.claude`, `~/.codex`, chat-history, or
agent-harness directory is not automatically an admissible research subject.
Home-directory exports can contain private source, credentials, internal hostnames,
personal data, third-party data, and material the uploader had no right to redistribute.
The presence of a Hugging Face download button is not consent to infer the uploader's
skills, organization, coworkers, or productivity.

Admit a real-user corpus only when all of these are true:

- the uploader explicitly describes the records as donated for research;
- the pinned revision has a license covering the relevant files and derived outputs;
- the consent and dataset card identify whether conversations, tool output, source
  code, and third-party content are covered;
- an automated and manual privacy review finds no live credential, access token,
  cookie, private key, credential-bearing URL, sensitive personal datum, or proprietary
  payload;
- the corpus exposes stable session/attempt boundaries without requiring an inferred
  real-world identity;
- erasure/contact instructions are available; and
- raw records remain quarantined, with only minimized event projections admitted to
  analysis.

Do not admit a raw home-directory snapshot when these conditions are absent. Do not
commit raw user records, embeddings, verbatim snippets, or reconstructed memory files.
For an admissible export, preserve only the approved harness files and a source
manifest. Treat `.env`, auth stores, browser profiles, shell histories, SSH material,
cloud config, unrelated dotfiles, and arbitrary filesystem attachments as denied by
default.

The currently identified Trace Commons corpus is useful as a small ecological stress
test because it contains donated sessions from human coding harnesses. Its 30 sessions
are not a population sample and usually lack independent outcomes. It can reveal parser
failures and organic patterns that synthetic traces miss; it cannot estimate prevalence
or validate enterprise-level benefit.

## Claims and evidence boundary

Use these result classes in the study database, paper, issue tracker, and UI:

- **R0 — reproduced observation:** a deterministic description of authorized evidence;
- **R1 — validated mechanism:** an analyzer meets a frozen benchmark against independent
  labels or a state checker;
- **R2 — ecological feasibility:** the mechanism can operate on minimized donated
  real-user traces, without claiming prevalence or benefit;
- **R3 — prospective enterprise effect:** a consented intervention changes an
  independently observed outcome under an identifiable design;
- **A — abstain:** evidence is missing, contradictory, out of scope, or too uncertain;
- **X — prohibited:** a workforce inference Frankengate must not make.

Public-data R1 plus real-user R2 does not imply R3. No number of retrospective traces
identifies what would have happened had a user received a different prompt, skill,
memory, tool, permission, route, or collaborator.

## Original enterprise questions as falsifiable studies

| Enterprise question | Retrospective result allowed | Prospective evidence required | Ground truth | Final claim ceiling |
|---|---|---|---|---|
| Can each user see all their own history? | Compare returned evidence with the capture manifest and permission oracle | A capture-coverage audit across real clients, failures, reconnects, deletion, and late objects | Source receipt counts, canonical IDs, explicit missingness, current authorization | R0: complete for named capture sources and interval, with explicit gaps |
| What friction repeated before eventual success? | Link same-task attempts and propose ordered recovery deltas with alternatives | Add/remove replay for replayable tasks or randomized suggestion exposure for live work | Independent task outcome, blinded delta labels, environment/model/permission changes | R1 for extraction; R3 only for a helpful intervention |
| Is the blocker a capability gap or the environment? | Emit competing hypotheses: knowledge, permission, tool, incident, model, policy, task ambiguity, insufficient evidence | Optional practical check or randomized support intervention after environment controls | Environment telemetry and policy decisions; expert label; user correction; optional task check | Never a person-level deficit label; at most “support X may help this task” |
| What should become an eval? | Convert an evidence-linked failure into exact, ordered, invariant, semantic, or state assertions and test seeded mutants | Rerun the changed agent/system against frozen cases before claiming regression protection | Mutant kill, allowed-variation false positive, independent state checker | R1 audit proposal; R3 release effect after rerun |
| Which prompt or skill should be suggested? | Generate an applicable candidate from disjoint success/failure evidence | Random no-help/relevant-help/placebo assignment with artifact exposure logged | Independently verified outcome, correction, cost, latency, unsafe action | R3 only |
| Who is doing similar work? | Retrieve deidentified task patterns and explain the matched dimensions | Reciprocal opt-in introduction around a minimized artifact | Blinded pair labels, user confirmation, mutual acceptance, post-introduction outcome | R1 task retrieval; R3 collaboration utility; never a named people search |
| What should become memory? | Propose cited, temporal, scoped facts or procedures; detect contradictions and stale claims | Randomized memory-on/off/placebo exposure on held-out tasks | Citation entailment, reviewer decision, exact exposure, verified outcome, delayed correction | R1 proposal quality; R3 utility |
| Should Frankengate adapt an embedding? | Identify a frozen hard-negative retrieval slice that general hybrid retrieval misses | Validate on consented tenant/user/time holdouts and after deletion/reclassification | Human pair labels, exact-ID preservation, authorized candidate oracle | R1 retrieval improvement, not user improvement |
| Should Frankengate fine-tune a model? | Identify a stable behavior that lower-cost interventions fail to fix | Governed training release plus prospective comparison with prompt/tool/skill/routing controls | External task outcome, memorization/deletion tests, rollback and regressions | R3 narrow behavior benefit only |
| Who is productive, competent, loyal, or likely to leave? | None | None | None | X: prohibited |

## Cohorts and dataset eligibility

### Tier A: benchmark-mechanism cohort

Use source-pinned, licensed partitions only:

- MCP ATIF fixtures and Frankengate-native conformance fixtures for loss and projection;
- CodeTraceBench verified rows for decisive-step and redundant-exploration labels;
- Nebius same-task success/failure attempts for signal and recovery pilots;
- AgentTrace for ordered tool execution and deterministic replay;
- SPARK PDI for observational fail-to-success sequences and procedure candidates;
- MATM ALFWorld for its paired retrieval-condition null and instrumented-rerun design;
- selected environment suites with reset/state verifiers for causal replay; and
- CMU only as private exploratory evidence until licensing and access terms permit
  publication.

Benchmark episodes test mechanism validity, not human ability or enterprise prevalence.
All inference is clustered at task, repository/template family, source, and model where
appropriate. Failed, truncated, crashed, and incomplete attempts remain outcomes or
typed missingness, never routine exclusions.

### Tier B: donated real-user ecological cohort

Begin with the smallest licensed donated set and a manual privacy audit of every
included session. The unit is the user-session or linked user-task, not the turn.
Report dataset selection, donor self-selection, source coverage, outcome missingness,
and every quarantine reason.

Tier B can test:

- whether importers preserve branched conversations, exact identifiers, tool messages,
  interruptions, and edits;
- whether frozen deterministic signals discover organic patterns absent from benchmark
  corpora;
- whether task, friction, eval, and memory candidate UIs can cite understandable
  evidence; and
- whether analyzers abstain when outcome, environment, or attempt linkage is missing.

Tier B cannot test:

- enterprise prevalence;
- cross-user usefulness when there are no stable, consented peer relationships;
- capability gaps;
- business outcomes;
- organizational demand; or
- causal benefit.

### Tier C: consented Frankengate enterprise cohort

Run an initial private, opt-in pilot before any team or enterprise release. The pilot
needs stable subject identity, source coverage, current authority, and at least one
independently observable outcome family. Users can inspect, correct, exclude, and
delete their evidence and derived candidates.

Do not choose a fixed sample size from convenience. Before enrollment:

1. specify the smallest effect worth acting on for each primary outcome;
2. estimate event rate, task repetition, intraclass correlation, and attrition in a
   blinded run-in period;
3. power the study at the assignment unit, including user/task clustering and planned
   multiple comparisons; and
4. publish the resulting enrollment target or label the study explicitly as a
   feasibility pilot.

A small pilot can establish capture reliability and proposal usability. It cannot be
promoted to an enterprise-effect claim because a confidence interval happens to exclude
zero in an underpowered, adaptively explored slice.

## Ground-truth hierarchy

Use the strongest available truth source and preserve disagreement:

1. **external state verifier:** environment state, test suite, transaction result,
   artifact hash, deployment health, policy decision, or other system independent of
   the agent;
2. **source outcome:** benchmark reward or harness result with documented semantics;
3. **blinded expert adjudication:** two independent labels plus adjudication, with
   evidence IDs and an insufficient-evidence option;
4. **user correction or confirmation:** authoritative for user intent and usefulness,
   but not proof of system state or causal outcome;
5. **model judge:** a versioned measurement instrument, never the sole ground truth.

For capability support, the label set is deliberately task-scoped:

```text
support is plausibly relevant
environment or permission explains the outcome
tool or model behavior explains the outcome
task specification is ambiguous
multiple explanations remain
insufficient evidence
```

There is no `user lacks skill` label. Optional practical checks measure performance on a
specific task under a specified environment; they do not establish a stable personal
trait.

Annotation hides treatment, source model, reward, signal-selection arm, and method
output where the label permits. Report agreement and retain uncertainty. Labels with
Krippendorff's alpha or weighted kappa below 0.67 remain exploratory after one rubric
revision. Critical shipping labels require at least 0.80 agreement.

## Minimal study sequence

### Study 0 — representation and permission qualification

Run benchmark, donated-user, and synthetic governed fixtures through:

```text
native -> canonical evidence DAG -> source-neutral rendering
                               -> ATIF + loss receipt
                               -> OTel + loss receipt
```

Primary endpoints:

- 100% preservation of tool proposal, authorization, execution, result, outcome, and
  governance events in gold fixtures;
- at least 99.5% typed-event and edge preservation;
- deterministic re-import;
- zero silent loss; and
- permission-oracle equality for rows, counts, snippets, cursors, object references,
  FTS, vector candidates, exports, caches, and deleted evidence.

Failure stops all downstream user, team, and enterprise claims.

### Study 1 — personal history and retrospective proposal quality

On Tier A and B, then in a Tier C shadow period, freeze and evaluate:

1. history completeness and missingness;
2. review selection against random and trace-length baselines;
3. task retrieval against exact+lexical+structured baselines;
4. decisive-step and friction diagnosis with calibrated abstention;
5. recovery-delta extraction;
6. eval proposal mutation testing; and
7. fact, memory, and procedure proposal citation/applicability.

No proposal changes a prompt, skill, memory, route, model, teammate, or live harness.
Users and reviewers see source evidence and alternatives. Their acceptance is a
usability outcome, not proof of causal value.

### Study 2 — replayable intervention qualification

For tasks with pinned environments, randomly assign:

- no intervention;
- the relevant generated artifact;
- an unrelated but superficially similar placebo; and
- an oracle artifact when available.

Hold retrieval fixed while testing artifact generation. Then hold the winning artifact
set fixed while testing retrieval/routing. Record exact artifact revision, prompt
injection, whether it was viewed/used, seed, environment reset, model parameters, and
external outcome. At least one independent verifier must be outside the generating and
judging model family.

This identifies an effect only for the pinned replay environment. It is a prerequisite,
not a substitute, for enterprise transfer.

### Study 3 — private prospective enterprise transfer

Run separate randomized or randomized-encouragement trials for:

1. eval suggestion;
2. prompt/skill/procedure suggestion;
3. memory suggestion;
4. optional task-scoped capability support; and
5. artifact-mediated reciprocal collaboration.

Do not vary all treatments together. Each trial has no-help, relevant-help, and placebo
arms where ethical and practical. If all users must receive an existing benefit, use a
stepped-wedge rollout or randomized encouragement and analyze intention to treat.

Primary outcomes are independently verified task success and serious harm. Secondary
outcomes include turns, correction cycles, time/cost conditional on success, user
acceptance, unsafe/privileged actions, delayed repeat success, and artifact rollback.
User satisfaction is important but does not replace the independent outcome.

### Study 4 — model adaptation gate

Run only after Studies 1–3:

- train a domain embedding adapter only when frozen hybrid retrieval has a named
  failure slice and purpose-authorized reviewed pairs/hard negatives;
- fine-tune a generator only when a stable prospective behavior remains after prompt,
  tool, skill, memory, retrieval, and routing alternatives.

Use tenant, user, task-family, source, and time holdouts. Test canary strings, verbatim
memorization, exact-ID retrieval, unauthorized-neighbor exclusion, deletion, subgroup
harm, rollback, and general-domain regression. A model trained on public successful
traces is a mechanism experiment, not an enterprise-adapted model.

## Metrics and stop rules

| Mechanism | Primary metric | Required comparator | Minimum continuation gate |
|---|---|---|---|
| Personal history | permission-oracle equality and capture completeness | source receipt manifest | zero scope leak; every absence typed as missing, denied, deleted, or unavailable |
| Review selection | informative precision at fixed budget and critical-case recall | random and trace length | at least +15 percentage points over random and no more than 10% critical miss after audit sampling |
| Task retrieval | Recall@20, nDCG@20, hard-negative error | exact+FTS+structured | dense/adapted arm continues only with a material frozen-slice gain |
| Diagnosis | top-1 decisive-step accuracy and selective risk | first-error, last-error, deterministic invariants | at least +10 points over deterministic baseline with calibrated abstention |
| Recovery delta | macro-F1 plus replay add/remove effect | unordered summary | no causal wording unless replay or prospective exposure changes the outcome |
| Eval proposal | mutant kill and allowed-variation false positives | deterministic-only and judge-only | meaningful kill gain without normal-variation brittleness |
| Memory proposal | citation entailment, factual precision, contradiction/time accuracy | verbatim retrieval and rolling summary | at least 99% citation support, 95% factual precision, zero scope leak |
| Procedure utility | intention-to-treat success and critical-slice harm | no-help, placebo, oracle | positive effect in at least two domains; no critical-slice harm above 5% |
| Collaboration | mutual opt-in, useful artifact exchange, later verified outcome | artifact-only/no-introduction | benefit must survive cohort/privacy controls; any identity leak stops release |
| Domain embedding | Recall@20 on frozen corporate hard slice | best general hybrid/reranker | at least +5 absolute points with no exact-ID, deletion, subgroup, latency, or rollback regression |
| Generator adaptation | prospective external outcome | prompt/tool/skill/memory/routing alternatives | improvement after cheaper controls fail; zero critical regression |

The Nebius signal pilot and MATM paired pilot are valid negative/ambiguous results:

- the fixed Nebius friction score did not beat trace length at the fixed review cutoff;
- no MATM reranked-retrieval depth had a reliable aggregate success advantage; and
- neither result justifies abandoning signals or memory, but both block inflated
  “trace intelligence already improves work” wording.

Continue only with a changed mechanism, a clearly different estimand, or more informative
instrumentation. Do not rerun losing analyses with new prompts until one appears
positive.

## Abstention and uncertainty contract

Every diagnosis, match, memory, eval, or intervention candidate returns:

- claim class and study tier;
- cited evidence IDs;
- observed versus reconstructed fields;
- alternatives and counterevidence;
- missing evidence;
- confidence calibrated on a frozen set;
- scope, purpose, classification, and expiry;
- whether causal utility has been tested; and
- an explicit abstention reason.

Required abstention reasons include:

```text
insufficient capture
unknown task linkage
missing outcome
environment changed
permission or policy confound
model or tool revision changed
multiple plausible causes
no authorized candidates
classification or purpose mismatch
stale authorization epoch
privacy release suppressed
out of validated domain
```

Evaluate risk as coverage falls. A system that achieves high accuracy by silently
dropping hard, denied, stale, or incomplete cases fails. Denial, zero matches, missing
derived state, and analyzer failure are distinct observable states.

## Causal analysis

The principal estimand for prospective studies is intention to treat at the randomized
assignment unit. Report treatment received as secondary because users may ignore,
edit, or partially use a suggestion.

- Pair identical replay tasks across arms when deterministic reset is credible.
- Cluster live uncertainty by user and task family; include time/block effects when
  rollout is staged.
- Report absolute effects and 95% cluster intervals, not only p-values.
- Correct preregistered confirmatory families with Holm; label slices exploratory.
- Record selection and exposure propensities.
- Use inverse-propensity or doubly robust estimates only when overlap, negative
  controls, and sensitivity analyses pass.
- Treat observational recovery sequences as candidate generators, never causal effects.
- Separate immediate task completion from delayed independent repetition; the latter is
  required for durable capability-support claims.

The unit is never a message, turn, span, or tool call. It is a task attempt, linked
attempt pair, replayed task, or randomized user-task exposure. Generated artifacts and
near duplicates cannot cross induction and evaluation folds.

## Privacy, RLS, and enterprise release

All raw and derived objects carry tenant, subject, audience, classification, purpose,
consent/training eligibility, current authorization epoch, retention/deletion state,
source evidence IDs, and derivation revision. Derived scope is the intersection of
source scopes and current policy.

Personal results remain private to the subject. Team membership does not authorize raw
peer traces. Cross-user analysis operates on separately reviewed minimized artifacts
and privacy-safe cohort releases. A named introduction requires reciprocal opt-in. An
enterprise view may show coverage-qualified task demand, recurring system/tool/policy
friction, missing shared artifacts, eval coverage, and intervention outcomes at
approved cohort granularity; it may not permit a pivot back to a person.

Test:

- stale epochs and mid-query membership removal;
- user/team/tenant and classification isolation;
- purpose and training-consent mismatch;
- FTS, exact-vector, ANN, snippets, counts, cursors, caches, and exports;
- classified evidence mixed into a candidate;
- deletion after derivation and before expansion;
- repeated aggregate differencing and one-person complements; and
- model output quoting unauthorized evidence.

Any cross-scope disclosure blocks team and enterprise release. Privacy controls are
not weakened to recover retrieval recall or statistical power.

## Deliverable result matrix

Publish this table for every run, including null and failed runs. A blank cell is not a
negative result; it is missing evidence.

| Question | Tier / design | N users / tasks / attempts | Comparator | Primary estimate [95% CI] | Ground-truth coverage | Abstention / missingness | Privacy/RLS result | Claim class | Decision |
|---|---|---:|---|---|---:|---:|---|---|---|
| Own-history completeness | C / capture audit |  | source manifest |  |  |  |  | R0/A |  |
| Informative review selection | A+B+C / frozen retrospective |  | random; length |  |  |  |  | R1/R2 |  |
| Same-task and related-task retrieval | A+B+C / held-out grouped |  | exact+FTS+structured |  |  |  |  | R1/R2 |  |
| Repeated friction and recovery delta | A+C / linked attempts; add/remove |  | unordered summary; placebo |  |  |  |  | R1/R3/A |  |
| Capability support vs environment blocker | C / optional randomized support |  | no-help; placebo |  |  |  |  | R3/A |  |
| Eval proposal | A+C / mutation then rerun |  | deterministic; judge-only |  |  |  |  | R1/R3 |  |
| Prompt/skill/procedure utility | A+C / randomized exposure |  | no-help; placebo; oracle |  |  |  |  | R3 |  |
| Memory proposal and utility | A+C / cited extraction then randomized exposure |  | verbatim; summary; placebo |  |  |  |  | R1/R3 |  |
| Cross-user similar work | C / deidentified retrieval |  | lexical/structured |  |  |  |  | R1 |  |
| Opt-in collaboration | C / randomized encouragement |  | artifact-only/no introduction |  |  |  |  | R3/A |  |
| Domain embedding adaptation | C / user+tenant+time holdout |  | best general hybrid |  |  |  |  | R1 |  |
| Generator fine-tune | C / prospective controlled release |  | cheaper interventions |  |  |  |  | R3 |  |

Each row links to:

- immutable source and code revisions;
- admission, privacy, and loss receipts;
- preregistration and exclusions;
- assignment/exposure manifest;
- analyzer, embedding, judge, artifact, and policy revisions;
- aggregate metrics and cluster uncertainty;
- slice and harm results;
- correction, deletion, and rollback status; and
- a plain-language statement of what is not supported.

## Direct answer to the enterprise objective

This study can establish that Frankengate:

1. faithfully shows a user their governed history;
2. finds review-worthy evidence and repeated recovery patterns;
3. separates plausible environment, permission, tool, model, and knowledge
   explanations while abstaining;
4. proposes evidence-linked evals, memories, prompts, and skills;
5. retrieves deidentified related work and supports reciprocal artifact-mediated
   collaboration; and
6. learns, prospectively, which reversible support helps which task contexts.

It cannot infer employee competence or organizational value from retrospective logs.
It cannot turn public benchmark or donated home-directory traces into enterprise
ground truth. It cannot claim memory, retrieval, embedding adaptation, or fine-tuning
helps until exact exposure and independent outcomes show that it does.

That boundary makes the research useful rather than smaller: public and donated data
can cheaply kill weak mechanisms, while the consented enterprise study spends user
attention only on mechanisms that have already passed representation, privacy,
retrieval, diagnosis, and replay gates.
