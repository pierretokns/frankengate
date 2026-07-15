# Agentic Flywheel Skill Feedback Loops

Status: primary-source research synthesis
Date: 2026-07-15

## Bottom line

Jeff Emanuel's published process is a real closed loop, not a metaphor:

`real task -> session trace -> structured feedback/outcome -> quality filtering -> pattern
mining -> skill rewrite -> failure-case validation -> deployment -> more real tasks`.

The recursive leverage comes from improving both the task skill and the meta-skill that
performs the refinement. Public materials describe three overlapping learning systems:
manual agent feedback forms, CASS/CM session mining into procedural knowledge, and JSM/
Meta Skill effectiveness data feeding context-aware skill selection.

## Publicly documented loops

### 1. Post-use agent feedback

After an agent uses a tool on real project work, ask it to score helpfulness, missed
issues, signal-to-noise, errors, usability, desired changes and recommendation strength.
Send that structured feedback to a fresh agent working on the tool. Emanuel explicitly
warns that requested future features are weaker evidence than behavior after an
implemented feature is used in real work.

Source: [Complete Flywheel Guide, Agent Feedback Forms](https://agent-flywheel.com/complete-guide).

### 2. CASS skill refinement

The published refinement recipe is:

1. Ship a useful but imperfect baseline skill.
2. Let multiple agents use it on real Beads and projects, not an isolated demonstration.
3. After roughly ten or more sessions, search CASS for the skill/tool.
4. Extract clarifying questions, skipped steps, repeated mistakes, invented workarounds
   and outright failures.
5. Give those cases and the current skill to a fresh agent; rewrite the happy path,
   guardrails and official workarounds.
6. Test the revised skill against the recorded failure cases.
7. Repeat; the guide claims material reliability improvement after three to four cycles.

Repeated prompts or procedures are treated as rituals only after evidence accumulates:
ten or more repetitions are considered validated methodology, five to nine an emerging
pattern, and fewer than five a non-generalizable one-off.

Source: [Complete Flywheel Guide, CASS-powered refinement and ritual detection](https://agent-flywheel.com/complete-guide).

### 3. Three-layer memory feedback

CASS stores episodic session history. A diary/summary layer creates working memory. CM
distills procedural playbook rules with confidence and maturity. Published behavior says
rules decay with a 90-day confidence half-life without feedback; harmful feedback counts
four times as strongly as helpful feedback; rules progress from candidate to established
to proven. This makes forgetting, negative evidence and maturity explicit rather than
allowing every extracted pattern to become permanent doctrine.

Source: [Complete Flywheel Guide, CASS Memory](https://agent-flywheel.com/complete-guide).

### 4. JSM/Meta Skill effectiveness data

The public Meta Skill repository describes four structured effectiveness signals:

- explicit helpful/unhelpful feedback, rating and comments;
- success/failure outcomes when a suggestion is acted upon;
- A/B experiment records for variants;
- session quality measures such as passing tests, clear resolution, backtracking and
  abandonment.

These signals influence skill pruning, graph weighting, which sessions are mined and
context-aware suggestions. The suggestion engine uses Thompson sampling: ranking signal
families act as arms, feedback updates beta distributions, UCB-style exploration avoids
premature convergence, context modifiers adjust weights, and a cold-start threshold
prevents trusting learned weights too early.

Source: [Dicklesworthstone/meta_skill](https://github.com/Dicklesworthstone/meta_skill).

### 5. Provenance-preserving skill generation

Meta Skill documents a CASS extraction pipeline that searches sessions, applies quality
filters, extracts patterns with uncertainty, synthesizes a structured skill, and links
rules back to source sessions. Bundles use checksums/per-file hashes and protect local
modifications from surprise overwrite. This is important: a generated instruction has
evidence lineage and distribution integrity, rather than appearing as unattributed prose.

Source: [Dicklesworthstone/meta_skill](https://github.com/Dicklesworthstone/meta_skill).

### 6. Post-implementation critique of the analysis itself

Emanuel published a detailed self-critique after using the modes-of-reasoning skill. It
identifies false convergence from shared evidence, threat-model miscalibration, padded
findings, impractical counterfactuals, failure to run code, and treating documented
limitations as discoveries. Proposed corrections include:

- require different evidence methods before calling agreement convergence;
- independently verify or try to disprove the highest-impact findings;
- calibrate severity to deployment context and project identity;
- separate known risks from discoveries;
- require dynamic execution, not static analysis alone;
- cap and action-gate findings;
- record accepted/rejected recommendations as a false-positive learning signal;
- revisit the analysis after implementation supplies ground truth.

This is direct evidence of the loop in practice: a skill run generates a retrospective,
the retrospective specifies concrete changes to the skill, and later uses are evaluated
against those failure modes.

Source: [feedback_on_modes_of_reasoning_skill.md](https://gist.github.com/Dicklesworthstone/a3b41385a88a1ccc368147e7365ecaa2).

## Current local JSM surfaces

The installed JSM 0.3.11 exposes the same conceptual layers:

- `jsm effectiveness record/show/recompute` for local outcome aggregates;
- `jsm cass search/show/list/mark/mine` for session mining and draft generation;
- `jsm telemetry enable/disable/status/show/flush/purge` for opt-in team usage events;
- `jsm graph` for keystones, bottlenecks, clusters and cycles;
- `jsm security` for ACIP scanning and quarantine;
- sync/update, evidence, validation and integrity surfaces for distribution.

The public repository currently uses the binary name `ms` in examples while our product
uses `jsm`; do not assume every documented command or schema maps one-to-one without
checking the installed version.

## What was not verified

- No authoritative public X post was located through web search that adds material detail
  beyond the guide, repository and gist. Searches under both `Dicklesworthstone` and the
  linked X handle `doodlestein` produced no reliable indexed match.
- Local XF archive search could not be used: no X archive/database is configured, and
  NTM 1.19.1's XF adapter still passes an obsolete `--output` flag to XF 0.3.2.
- The public material describes the intended feedback architecture. It does not prove
  which production Jeffreys-Skills/JSM server-side jobs run continuously, their sample
  sizes, or whether bandit suggestions currently change published skill content
  automatically. Treat that as unverified implementation detail.

## What to adopt for the gateway skill marketplace

Use the loop, but strengthen its governance:

1. Record every invocation against immutable skill/model/tool/policy revisions.
2. Capture objective terminal results, deterministic checks, user report, behavioral
   friction and model-judge evidence as separate typed observations.
3. Sample successes as well as failures and publish missingness/inclusion probabilities.
4. Mine only privacy-eligible, tenant-authorized sanitized traces.
5. Generate multiple candidate revisions; never let the proposing model approve itself.
6. Replay historical failures plus untouched holdouts and critical slices.
7. Require two evidence methods for a kernel finding; run a kill-thesis counter-search.
8. Shadow and tenant-sticky canary the revision with hard safety/privacy floors.
9. Promote through a signed receipt; retain instant rollback and an observation window.
10. Feed accepted, rejected, regressed and rolled-back proposals into future selection.
11. Decay stale rules and weight harmful outcomes asymmetrically, but calibrate those
    constants empirically rather than copying 90-day/4x values blindly.
12. Keep suggestion ranking separate from publication authorization. A bandit may decide
    what to try next; it must never decide what becomes enterprise-approved by itself.

This creates compounding leverage without converting a noisy self-referential feedback
loop into an automated supply-chain or policy escalation mechanism.
