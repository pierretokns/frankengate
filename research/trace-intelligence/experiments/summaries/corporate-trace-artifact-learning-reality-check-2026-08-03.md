# Corporate trace-artifact learning: reality check

**Purpose:** consolidate the empirical program into claim-level evidence rather
than treating a working prototype, a retrieval score, or a model-generated
JSON response as proof of enterprise utility.

## Current claim boundary

The program has demonstrated that Frankengate can preserve, filter, retrieve,
review, replay, and independently verify trace-derived candidates. It has not
demonstrated that automatically mined skills, memories, embeddings, or
cross-user recommendations improve real enterprise work. The remaining gap is
not primarily database choice; it is outcome-labelled, identity-aware,
changed-environment evaluation.

## Evidence by enterprise question

| Enterprise question | Current evidence | Status | What would change the status |
| --- | --- | --- | --- |
| What work is this user doing? | Canonical trajectory projections, exact identifiers, normalized tool shapes, and lexical retrieval recover bounded structural patterns. | **Mechanically supported** | Consent-backed user labels and a prospective usefulness study. |
| Where does a user repeatedly struggle? | Rephrase, retry, correction, error, and malformed-event detectors produce review queues; tool-result edges are missing in one public coding export. | **Candidate mining only** | Typed tool-result chains plus blinded friction/outcome labels. |
| Which traces should become evals? | Structural recovery and eval proposal queues are reproducible; independent verification passes format/grounding gates. | **Proposal mechanics supported** | Execute generated evals on changed systems and measure precision, recall, repair cost, and regression rate. |
| Can a validated SQL/tool artifact be reused? | Governed capsules, parameter binding, authority checks, expiry, schema checks, and replay work. Natural nearest-artifact transfer was `0/10` because the library lacked matching intent; controlled known-match paraphrases recovered `20/20`. | **Mechanics supported; coverage-limited utility** | Parameterized/composable artifacts, regeneration controls, and changed-schema replay. |
| Do skills improve future task outcomes? | Disjoint Trace2Skill replay tied controls (`3/4`); multiple SkillOpt/memory/RHO slices were null or negative; one enterprise-search procedure was directional but not causal. | **Not established** | Powered family/user/time-disjoint factorial with no-skill, placebo, human, mined, SkillOpt, SkillGen, RHO, and regeneration arms. |
| Do embeddings find similar work across users? | Exact identifiers and structured scope consistently beat generic dense retrieval on collision slices; dense recall helps after structured filtering. | **Structured retrieval supported; semantic equivalence unproven** | SME-labelled same-task/alias/NIL sets with user/project/time holdouts. |
| Does a custom embedding help? | Small adapters were null or worse on proxy labels. The Oracle six-model recipe is reproducible as a selection mechanism, but LaBSE's extra coverage did not improve reranker MRR. | **Not promotion-ready** | Blinded corporate hard-negative labels and an absolute uplift gate against the structured baseline. |
| Can the system infer missing skills? | Capability/skill-gap analysis mechanics exist on authorized content-free cohorts. | **Analysis mechanics only** | Reviewed capability taxonomy, environment-availability labels, abstention, and prospective task uplift. |
| Can the system recommend collaboration? | Authorized aggregation and minimum-cohort gates work. | **Mechanics only** | Reciprocal opt-in, privacy review, and independently measured introductions/outcomes. |
| Should memory files be written automatically? | Memory/skill files can be imported with provenance; writes correlate with later recurrence but are confounded. | **Do not auto-promote** | Bitemporal contradiction, citation, deletion, rollback, and randomized changed-system utility tests. |

## Embedding and hard-negative result

The Oracle paper's six-model composite was implemented with pinned public
checkpoints and its two inequalities. On the bounded TechQA fixture:

| Arm | Inequality-valid candidates | Same reranker MRR@10 |
| --- | ---: | ---: |
| LaBSE | `56/100` | `.6936` |
| Six-model composite | `23/100` | `.6950` |

The annotated audit found no selected negative that appeared in the fixture's
published `gold_page_ids` (`0/56` and `0/23`). That is not a relevance oracle;
unmarked pages can still be relevant. LaBSE's result therefore means “broader
candidate coverage under this geometry,” not “better enterprise embedding.”
See [`hard-negative-annotated-false-negative-audit-2026-08-03.md`](hard-negative-annotated-false-negative-audit-2026-08-03.md).

## What works well together

The strongest composition is:

```text
canonical trajectory DAG
  -> consent / authority / deletion gate
  -> exact identifiers + scope + lexical retrieval
  -> optional dense candidate recall
  -> identifier-aware rerank
  -> frontier or SME review only for ambiguous/high-value cases
  -> typed artifact/eval proposal
  -> independent verifier + isolated replay
  -> prospective outcome and rollback gate
```

This composition is supported by separate receipts for trajectory fidelity,
authority filtering, structured retrieval, bounded frontier review, governed
capsules, and independent replay. The receipts do not establish that every
candidate survives the final outcome gate.

## Hard edges

1. **Coverage is not correctness.** Inequality-valid negatives, recurring tool
   shapes, nearest prompts, and model agreement are candidate selectors only.
2. **Public labels are not enterprise semantics.** TechQA, Defog, FinanceBench,
   and DataClaw provide useful fixtures but lack corporate aliases, principals,
   epochs, tool outcomes, and changed-system outcomes.
3. **Embeddings do not preserve authority or identity.** They can collapse
   acronyms, same-scope siblings, versions, or renamed systems; exact and
   structured lanes must remain authoritative.
4. **A missing artifact library cannot be fixed by reranking.** The natural
   `0/10` transfer result was primarily a coverage ceiling, so add composable
   templates or regeneration before judging a model.
5. **Generated skills can dilute reviewed procedures.** Controlled rename
   probes show composition can retain capability but also introduce misses;
   negative-transfer gates are mandatory.
6. **A model-generated ontology is a proposal.** One-shot graphs lack stable
   identity, temporal validity, NIL handling, authority, and replay evidence.
7. **Memory-write correlation is not causality.** Users who write memory files
   are a selected cohort; only randomized changed-system replay can attribute
   an outcome to the memory.

## Smallest defensible architecture

Keep one governed PostgreSQL/Aurora evidence and experiment authority, one
loss-aware trajectory representation, exact/lexical/structured retrieval, and
optional pgvector behind those filters. Keep custom embeddings, Graphiti,
TurboVec/VectorChord/pgContext, automatic memory writes, and cross-user
recommendations in experiment branches until they clear the same outcome gate.

## Decisive next experiment

Build a sealed, consented, family-/project-/user-/time-disjoint cohort with:

- reviewed aliases, same-token/different-system collisions, NILs, and temporal
  renames;
- validated parameterized SQL/tool capsules plus a regeneration control;
- no-skill, neutral, formatting placebo, human, mined, SkillOpt, SkillGen,
  RHO, and compositional arms;
- exact/lexical/structured, dense, composite-hard-negative, and frontier-rerank
  retrieval arms on one fixed candidate pool;
- independent semantic, security, authority, and changed-schema/tool replay;
- task success, repair/regression, latency, cost, false-negative, and human
  usefulness metrics.

Until this experiment is complete, the scientifically correct product claim is
“governed evidence-to-artifact proposal and replay,” not “automatic enterprise
skill learning.”
