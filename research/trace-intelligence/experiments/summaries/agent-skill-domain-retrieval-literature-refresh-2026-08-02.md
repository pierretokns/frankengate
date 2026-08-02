# Agent-skill and domain-retrieval literature refresh

**Scope:** recent primary sources that change the design of corporate trace
artifact learning. These are mechanism transfers, not evidence that private
enterprise traces will produce useful skills without labels and changed-system
outcomes.

## Sources that materially sharpen the program

| Source | What it contributes | Frankengate adaptation | Hard edge |
|---|---|---|---|
| [From Raw Experience to Skill Consumption](https://www.microsoft.com/en-us/research/publication/from-raw-experience-to-skill-consumption-a-systematic-study-of-model-generated-agent-skills/) | Evaluates experience generation, skill extraction, and skill consumption together; reports average benefit with non-trivial negative transfer and proposes a meta-skill that targets utility-linked properties. | Add extractor × consumer factorials, utility-feature annotations, negative-transfer gates, and a meta-skill proposal arm. Score later-task outcomes, not skill-text quality. | Its domains and evaluators are not governed SQL/tool systems; the reported average lift does not transfer automatically. |
| [Trace2Skill: Verifier-Guided Skill Evolution for Long-Context EDA Agents](https://arxiv.org/abs/2605.21810) | Uses trajectory-local failure lessons plus bounded verifier feedback to evolve skills without weight updates. | Expose sanitized SQL/tool verifier signals: error class, authority rejection, schema mismatch, result-shape mismatch, and repair success. Keep hidden rows, credentials, and gold queries outside the proposer. | Verifier signals can leak task answers or authority; every signal needs an egress/taint contract and independent replay. |
| [Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills](https://arxiv.org/abs/2603.25158) | Parallel analysis of diverse trajectories followed by conflict-free hierarchical consolidation; reports cross-model/OOD transfer. | Mine per-trajectory lessons in parallel, consolidate only after contradiction and scope checks, and test source-project → held-out-project transfer. | Spreadsheet/math/VQA tasks do not establish artifact relevance, identity, or enterprise authorization. |
| [Harnessing Agent Skills: Architectural Patterns and a Reference Architecture](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6871959) | Defines the run-specific **skill-in-use** relation: selection, binding, interpretation, execution evidence, verification, repair, and evolution. | Make every proposal carry activation, bound authority/scope, observed use, verifier result, and rollback lineage; distinguish a stored skill from its use in a run. | SSRN architecture guidance is not a measured utility result and does not define our database/replay contract. |
| [Re-TRAC](https://openreview.net/forum?id=wjNTbZKIvC) | Cross-trajectory structured state records evidence, uncertainty, failures, and next plans to reduce redundant exploration. | Store a compact, time-bounded exploration state beside traces; use it for candidate generation and failure clustering, never as an authority or memory write. | Research-agent web tasks differ from corporate tools; state summaries can become future leakage or stale context. |
| [LogNER](https://doi.org/10.1016/j.jss.2026.112892) | LLM-driven entity recognition for noisy log semantics and domain terminology. | Extract candidate systems, resources, versions, and event entities before embedding; retain source spans/hashes and require review for alias edges. | Entity extraction is not entity linking: a recognized nickname still needs scope, temporal lineage, and NIL/wrong-system labels. |
| [Linking with Bias](https://doi.org/10.3233/SSW250015) | Finds that entity-linker quality varies by domain and no single linker dominates across domains. | Calibrate per tenant/domain and hold out projects/time; report abstention and collision rates rather than one global score. | The benchmark studies public entity linking, not agent traces or executable artifacts. |
| [Agent Trajectory Explorer](https://doi.org/10.1609/aaai.v39i28.35350) | Human-facing visualization and annotation of agent trajectories. | Use it as a reviewer workflow for friction, alias/NIL, and artifact relevance labels; export only content-minimized labels and provenance. | Annotation tooling does not supply reliable labels by itself; reviewer agreement and adjudication remain required. |

## What changes in the empirical design

The next skill study must separate four effects that prior one-shot runs
confounded:

1. **Extraction:** can a method identify a useful lesson from a completed trace?
2. **Binding:** does it activate only for the right scope, system, version, and
   task family?
3. **Consumption:** does a target model use it correctly under a changed system?
4. **Outcome:** does it improve a held-out task without negative transfer?

The minimum factorial is:

```text
no skill | formatting placebo | reviewed artifact | generated skill
         × no verifier | sanitized verifier | full independent replay
         × same-family | project-held-out | changed-schema/authority-held-out
```

Every arm needs the same task horizon, tool protocol, model/harness, cost
budget, and evaluator. A generated skill can be structurally valid and still
be quarantined if it loses to no-skill or creates an unsafe/wrong-system
acceptance.

## New reusable verifier contract

The verifier should return only a typed, bounded observation:

```text
{ outcome_class, error_class, authority_class, schema_class,
  result_shape_hash, repair_count, next_action_allowed }
```

It must not expose raw rows, secrets, hidden gold SQL, or unrestricted error
text. Store the observation as evidence attached to the run, not as a mutable
memory entry. A skill proposal may cite the observation, but an independent
replay service—not the proposer—decides whether it is correct.

## Evidence boundary

These recent sources strengthen the *mechanism* case for utility-grounded skill
consumption, verifier feedback, domain entity extraction, and run-level
provenance. They do not close Frankengate's open gates: enterprise alias/NIL
truth, same-work precision, prospective user benefit, cross-user collaboration
utility, or causal improvement on changed systems.

## Tracking

- Skill lifecycle and transfer: [#111](https://github.com/pierretokns/frankengate/issues/111)
- Validated artifact reuse: [#119](https://github.com/pierretokns/frankengate/issues/119)
- Embedding adaptation: [#121](https://github.com/pierretokns/frankengate/issues/121)
- Alias/hard-negative mining: [#123](https://github.com/pierretokns/frankengate/issues/123)
