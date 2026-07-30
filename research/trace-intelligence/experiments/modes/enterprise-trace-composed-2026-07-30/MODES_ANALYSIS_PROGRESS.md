# Modes-of-Reasoning Analysis Progress

## Status: Phase 6 complete; ten-mode synthesis published

## Started

2026-07-30T22:15:00Z

## Project

Frankengate enterprise trace intelligence research, in the dedicated
`codex/trace-intelligence-academic-program` worktree.

## Phase 0: Context Pack

- [x] Repository and research program profiled.
- [x] Deployment context recorded.
- [x] Core substrate and project values recorded.
- [x] Owner-acknowledged limitations separated from new findings.

### Project brief

Frankengate is an internal, multi-tenant AI gateway and dashboard. The research
program is testing whether governed agent traces can answer useful enterprise
questions: what people are working on; who is doing structurally similar work;
where users repeatedly encounter friction before success; which cloud,
database, or harness skills are missing; which prompts, tools, skills, memories,
or models would improve outcomes; and what evidence can safely become a
user-, team-, or enterprise-scoped `MEMORY.md`-style artifact.

### Deployment context

- Internal enterprise service, not a public trace-analysis product.
- Users see their own traces; authorized team and enterprise views are
  policy-bound; authorized admins may see full PII and classified content.
- Credentials and reusable authentication material are always excluded from
  the ordinary trace plane.
- Several hundred GB of logs/traces initially, with growth expected.
- Frankengate and its governance plane remain the enforcement point.
- The preferred result is the smallest operational architecture that answers
  the questions well; Aurora PostgreSQL is a starting constraint, not a
  religious requirement.

### Core substrate

The core substrate is governed, full-fidelity, tool-call-complete trace
evidence with explicit user/team/enterprise authority and time semantics.
Removing governance, provenance, or tool-call fidelity would change what the
system is. A particular search engine, vector database, memory framework, or
embedding model is replaceable.

### Systems and concepts in scope

- Trace representation and lifecycle: ATIF, OpenTelemetry/OpenInference,
  AgentRx, AgentEvals, Phoenix, Opik, Langfuse, OpenRCA.
- Cheap signal mining: rephrasing, stagnation, loops, tool failures,
  disengagement, recovery, and success transitions.
- Memory and knowledge: Graphiti, LangMem, MemInsight, Memory Palace,
  `MEMORY.md`, temporal/bitemporal evidence, contradiction and deletion.
- Dreaming and self-improvement: cloud-dreaming concepts, ReasoningBank,
  Hermes/Jeopard-style skill learning, RL-environment histories, governed
  proposal/review/release loops.
- Local/private history UX: CASS, Doodlestein/CM, claude-history,
  Prompt-Scope, conversation importers, Frankensearch concepts.
- Search/storage: Aurora PostgreSQL, JSONB, full-text search, pgvector,
  VectorChord viability, pg_textsearch, pgContext, Turbovec, Turbopuffer,
  SQL-based hybrid retrieval, and only justified external systems.
- Domain test beds: real agentic coding/research histories and enterprise
  NL2SQL traces, including tool calls and longitudinal memory files.
- Representation learning: off-the-shelf and enterprise-adapted embedding
  models, supervised/contrastive adaptation, and evaluation against exact
  identifier plus semantic retrieval.

### Existing empirical evidence

- Canonical schema/adapters, public-history fidelity, governed PostgreSQL
  retrieval, OpenTelemetry round trips, NL2SQL capability isolation,
  bitemporal conformance, tool-sandboxing, and combined-evidence experiments
  already exist under `research/trace-intelligence`.
- The completed 17-unit / 425-call longitudinal pilot is mechanics evidence,
  not a valid memory-arm comparison; all evidence-bearing labels behaved
  identically and the empty arm exposed a scoring artifact.
- Corrected v2 primitives now separately implement a credential-clean source
  boundary, cutoff-safe project identity, online temporal oracle,
  query-independent proposal release, blinded state packs, whole-item budgets,
  and runtime attestation. No corrected model result exists yet.

### Owner-acknowledged limitations

- Current 17-unit cohort is too small and has only two independent source
  families.
- Fable mirrors are not independent sources.
- The first pilot did not implement a real dream treatment, true bitemporal
  state, strict blinding, or launch attestation.
- Semantic similarity alone cannot establish identity, permission, causality,
  skill deficiency, or human intent.
- No current evidence supports moving off Aurora or training a custom
  embedding model.
- PII over-redaction was an architectural mistake; credentials are the narrow
  always-excluded class.

### Success criteria for this analysis

1. Evaluate each concept alone against a named enterprise question and
   measurable outcome.
2. Evaluate meaningful combinations, including negative interactions and
   non-composable concepts.
3. Separate deterministic signals, retrieval, reasoning, memory proposal,
   human review, and organizational intervention effects.
4. Produce a minimal architecture decision with explicit triggers for adding
   or replacing components.
5. Define an empirical factorial program using current public traces and
   NL2SQL traces, including causal limits and source/project clustering.
6. Identify which original enterprise questions remain unanswerable even if
   every proposed component works.

## Phase 1: Mode Selection

### Load-bearing axes

- Ampliative versus non-ampliative: discover patterns, then prove protocol and
  inference invariants.
- Descriptive versus normative: distinguish observed work patterns from claims
  about what skills or behavior users ought to adopt.
- Belief versus action: separate what the trace evidence supports from which
  intervention Frankengate should take.
- Single-agent versus multi-agent: individual assistance, team coordination,
  admin governance, and organizational incentives interact.
- Truth versus adoption: a technically correct system that users distrust or
  that managers misuse is a failed system.

### Selected modes

1. K2 Scientific Reasoning
2. A1 Deductive Inference
3. B3 Bayesian Reasoning
4. F1 Causal Inference
5. F7 Systems Thinking
6. G6 Multi-Criteria Decision
7. B9 Simplicity / Minimum Description Length
8. H2 Adversarial Review
9. I4 Perspective-Taking
10. L2 Debiasing

The antagonistic pairs are simplicity versus systems thinking and adversarial
review versus perspective-taking. Scientific/Bayesian/causal modes challenge
one another on what the current datasets can actually establish. Deduction
tests compositional invariants; multi-criteria reasoning forces architecture,
cost, scale, usefulness, and operational burden into one decision.

## Phase 2: Spawn

- [x] NTM session `frankengate-trace-research` created.
- [x] Ten agents visible in the robot snapshot.
- [x] Stale recovery work detected in four panes, interrupted, and accidental
  dependency-only churn preserved in a named recoverable stash.

## Phase 3: Dispatch

- [x] Ten distinct mode prompts sent.
- [x] Analysis-only scope reasserted after verifying pane output.

## Phase 4: Monitor

- [x] Outputs monitored for evidence quality and mode fidelity.

## Phase 5: Collect

- [x] Every substantive output read completely.
- [x] High-impact findings independently verified.
- [x] Contribution and provenance recorded in `MODE_SYNTHESIS.md`.

## Phase 6: Synthesize

- [x] Combined feasibility report written in `MODE_SYNTHESIS.md`.
- [x] Standalone and factorial experiment matrix written in
  `docs/roadmap/research/enterprise-trace-intelligence-independent-and-composed-program-2026.md`.
- [x] Minimal architecture and decision triggers written.

## Recovery Notes

Continue from Phase 2. All mode agents are analysis-only and must write one
unique `MODE_OUTPUT_*.md` file into this directory without modifying any other
project file.
