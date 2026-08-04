# Enterprise Trace Intelligence Mode-Agent Dispatch

Every agent must first read:

1. `AGENTS.md`
2. `research/trace-intelligence/README.md`
3. `research/trace-intelligence/experiments/modes/enterprise-trace-composed-2026-07-30/MODES_ANALYSIS_PROGRESS.md`
4. Relevant existing experiment summaries, configs, implementations, tests, and
   source citations under `research/trace-intelligence`.

This is analysis only. Do not modify code, configs, tests, beads, issues, or any
file except the single output assigned below. Do not browse merely to repeat
project citations; use primary sources when a factual claim requires current
verification. Treat owner-documented limitations as confirmed known risks, not
new discoveries.

## Shared question

Assess the complete Frankengate enterprise trace-intelligence program, not only
the corrected memory replication. Analyze each concept independently and in
meaningful combinations:

- ATIF, OpenTelemetry/OpenInference, AgentRx, Signals, AgentEvals, Phoenix,
  Opik, Langfuse, OpenRCA;
- Graphiti, LangMem, MemInsight, Memory Palace, temporal evidence, `MEMORY.md`;
- cloud dreaming, ReasoningBank, Hermes/Jeopard-style skill learning, and
  reinforcement-learning environment histories;
- CASS, Doodlestein/CM, claude-history, Prompt-Scope, Frankensearch;
- JSONB/full-text/vector/hybrid retrieval across Aurora PostgreSQL, pgvector,
  VectorChord, pg_textsearch, pgContext, Turbovec, and Turbopuffer;
- general embedding models versus enterprise-adapted embeddings;
- agentic coding/research traces and NL2SQL traces with complete tool calls.

For each important concept and combination, ask:

1. Which original enterprise question does it answer?
2. What observable evidence and labels does it require?
3. What does it answer deterministically, statistically, causally, or only as a
   hypothesis?
4. Which other components does it compose with, and at what interface?
5. Which combinations double-count evidence, leak future information, destroy
   provenance, conflate identity with similarity, or create circular feedback?
6. What is the smallest architecture that can test it?
7. What empirical standalone and factorial experiment would falsify its value?
8. What result would justify leaving Aurora or training an embedding model?
9. Which desired questions remain impossible or socially unsafe to infer?

The deployment is an internal enterprise tool. Authorized users, teams, and
admins may see full PII/classified content inside their scope. Credentials are
excluded from the ordinary trace plane. Calibrate risks against that actual
context.

## Output contract

Write only your assigned output file. Use:

```markdown
# [Mode] Analysis

## Thesis
## Top Findings
## Standalone Concept Assessment
## Composition and Non-Composition Matrix
## Enterprise Questions Answered and Not Answered
## Empirical Tests and Falsifiers
## Architecture Consequences
## Risks Identified
## Recommendations
## New Ideas and Extensions
## Assumptions Ledger
## Questions for Project Owner
## Points of Uncertainty
## Agreements and Tensions with Other Perspectives
## Confidence
```

Produce 5–8 numbered findings with `§F[N]` identifiers. Every finding needs
specific project or primary-source evidence, a reasoning chain, deployment-
calibrated severity, confidence, and a concrete “so what.” Explicitly mark
kernel candidates, hypotheses, and owner-acknowledged limitations. Include
negative results and concepts that should not be built.

## Ensemble

The ten modes are K2 Scientific, A1 Deductive, B3 Bayesian, F1 Causal
Inference, F7 Systems Thinking, G6 Multi-Criteria Decision, B9 Simplicity/MDL,
H2 Adversarial Review, I4 Perspective-Taking, and L2 Debiasing. Explain where
your mode should agree or disagree with at least two others.

## Assignments

### Pane 1 — K2 Scientific Reasoning

Output: `MODE_OUTPUT_K2_SCIENTIFIC.md`

Treat every proposed component and enterprise insight as a falsifiable claim.
Audit construct validity, cohort independence, labels, controls, factorial
design, leakage, and external validity. Produce a sequenced empirical program
that compares mechanisms alone and together without pretending model calls are
independent samples.

### Pane 2 — A1 Deductive Inference

Output: `MODE_OUTPUT_A1_DEDUCTIVE.md`

Formalize the premises required to move from traces to claims about same work,
skill gaps, friction, memory, or intervention benefit. Find invalid implication
chains and compositional contradictions. State invariants for authority,
identity, time, provenance, tool calls, deletion, and feedback loops.

### Pane 3 — B3 Bayesian Reasoning

Output: `MODE_OUTPUT_B3_BAYESIAN.md`

Represent what can be learned sequentially from sparse, biased enterprise
traces. Identify priors, likelihood evidence, source dependence, uncertainty
about uncertainty, and posterior calibration. Distinguish evidence worth
collecting from expensive signals that barely update belief.

### Pane 4 — F1 Causal Inference

Output: `MODE_OUTPUT_F1_CAUSAL.md`

Separate prediction and retrieval from causal claims that a missing skill,
prompt, memory, tool, or model caused an outcome. Draw the needed intervention
structure, confounders, selection mechanisms, mediators, and feasible
randomized or quasi-experimental designs.

### Pane 5 — F7 Systems Thinking

Output: `MODE_OUTPUT_F7_SYSTEMS.md`

Map the end-to-end feedback system: capture, canonicalization, signals,
retrieval, diagnosis, memories, skills, recommendations, evaluation, release,
withdrawal, and organization-level learning. Identify reinforcing loops,
delays, shared-state hazards, emergent behavior, and leverage points.

### Pane 6 — G6 Multi-Criteria Decision

Output: `MODE_OUTPUT_G6_MULTICRITERIA.md`

Build a decision model across answer quality, exact-term fidelity, temporal and
authority correctness, latency, ingest/query cost, operational burden,
Aurora compatibility, scale, deletion, RLS, and scientific usefulness. Rank
minimal architectures and define evidence-triggered upgrade thresholds.

### Pane 7 — B9 Simplicity / MDL

Output: `MODE_OUTPUT_B9_SIMPLICITY.md`

Find the smallest coherent system that can answer the original questions.
Demand proof before adding a database, graph, vector store, custom embedding,
LLM judge, or memory framework. Also identify where apparent simplification
would erase a load-bearing capability. Do not call anything dead or redundant
without multiple evidence methods.

### Pane 8 — H2 Adversarial Review

Output: `MODE_OUTPUT_H2_ADVERSARIAL.md`

Try to make the combined system produce confident but wrong organizational
conclusions, cross-scope contamination, circular training data, surveillance
misuse, poisoned memories, false skill-gap claims, and misleading causal
stories. Pair each realistic attack/failure with a test or containment rule.

### Pane 9 — I4 Perspective-Taking

Output: `MODE_OUTPUT_I4_PERSPECTIVES.md`

Analyze at least: individual contributor, team lead, enterprise admin,
privacy/security owner, evaluation scientist, and platform operator. Determine
which insights each needs, fears, will trust, can contest, and can act on.
Focus on adoption and on avoiding managerial misuse of uncertain inferences.

### Pane 10 — L2 Debiasing

Output: `MODE_OUTPUT_L2_DEBIASING.md`

Audit the entire research trajectory for confirmation, survivorship, selection,
availability, automation, sunk-cost, metric, and framework-collection bias.
Challenge both “Postgres can do everything” and “we need advanced vector/
memory infrastructure.” Identify what evidence would genuinely reverse the
current architecture or research priorities.
