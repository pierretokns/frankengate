# Ten-Mode Synthesis: Enterprise Trace Intelligence

## Scope

Ten reasoning modes independently assessed the full Frankengate trace
intelligence program:

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

The analysis covered trace formats, selectors, diagnosis, evaluation
lifecycles, memory, dreaming, skill learning, RL environments, personal history
tools, search and storage, embeddings, coding/research traces, and NL2SQL.

## Consensus

All ten modes converge on the same current architecture and claim ceiling:

- one governed canonical evidence and release authority in Aurora/PostgreSQL;
- exact, structured, and lexical retrieval first, with bounded general dense
  retrieval as a candidate lane;
- object storage for large immutable payloads and replay artifacts;
- asynchronous analysis workers isolated from the inference path;
- ATIF, OTel/OpenInference, AgentEvals, memory files, graphs, and search
  services as projections or experimental arms;
- personal history and evidence-linked proposal workflows before automatic or
  people-facing intelligence;
- no claim that the current evidence proves memory benefit, skill benefit,
  root cause, collaborator utility, enterprise embedding value, or a need to
  leave Aurora.

This agreement is unusually strong because it was reached for different
reasons:

| Mode | Why it reaches the common decision |
|---|---|
| K2 Scientific | Current experiments establish mechanics more often than constructs or outcomes |
| A1 Deductive | Retrieval, association, projection, and proposal lack the premises required for identity, cause, authority, and benefit |
| B3 Bayesian | Current evidence strongly updates mechanics but barely updates enterprise utility; source dependence is high |
| F1 Causal | Passive traces do not supply counterfactuals; interventions need exposure, controls, and independent outcomes |
| F7 Systems | Duplicate authorities and unmarked feedback create stale state and self-validation |
| G6 Multi-Criteria | One authority scores best on authority, deletion, exactness, operations, and current evidence |
| B9 Simplicity | Additional stores/frameworks increase total proof and rollback complexity before answering new questions |
| H2 Adversarial | Side channels, false organizational narratives, and poisoned feedback appear at cross-system boundaries |
| I4 Perspectives | Personal-first, artifact-first, contestable workflows are the only current path to user and operator trust |
| L2 Debiasing | Framework collection, public-corpus availability, metric laundering, and sunk cost would otherwise distort the roadmap |

## Independently verified evidence

The synthesis checked the high-impact claims against the project result
summaries and code rather than relying only on the mode outputs.

| Claim | Verified evidence | Conclusion |
|---|---|---|
| OTel is a strong operational projection | Real 12-trace / 48-span SDK -> Collector -> file -> reimport result retained the tested projected IDs, parents, links, and status | Supported for the tested projection; not a canonical evidence claim |
| ATIF is not the enterprise canonical store | The enterprise stress projection retained 0/48 canonical IDs and 0/34 parent edges after reimport while emitting losses | Supported |
| Signals do not yet beat simple baselines | Nebius and CodeTrace selection results did not reliably beat length/stage baselines | Supported |
| Current diagnosis composition is weak | On 35 aligned traces, the no-factor/reverse-chronology baselines beat the full deterministic combination | Supported negative result |
| Dense retrieval is conditional, not dominant | Structured+dense beat exact on silver labels; dense alone added little; local hybrid added negligible recall at about 250 ms extra p50 | Supported, limited by labels and scale |
| Current memory pilot did not test memory or dreaming validly | Evidence arms behaved identically; dream did not dream; no-memory score was an abstention artifact | Supported negative/invalid result |
| Relational temporal/release mechanics work locally | Synthetic bitemporal, forced-RLS release, and concurrency tests exist; the concurrency result records remaining gaps | Supported as mechanics only |
| Current NL2SQL skill result is null and protocol-blocked | All three arms passed the same 2/4 tasks; protocol failures were 25-50% | Supported |
| Public corpora do not form an enterprise panel | Source audits show mirrors, flattened derivatives, scrubbed histories, and concentrated source families | Supported |
| Aurora sufficiency is not proven | Current database evidence is local PostgreSQL mechanics, not Aurora failover/RDS Proxy/selective-RLS production load | Supported limitation |

## The system model

The modes jointly imply this typed flow:

```text
observed source
  -> loss-aware canonical event DAG
  -> current authority and deletion gate
  -> deterministic selector
  -> authorized retrieval candidate
  -> diagnosis hypothesis
  -> eval / memory / skill / artifact proposal
  -> independent review and immutable release
  -> controlled exposure
  -> later outcome and harm measurement
  -> independent validation, revision, withdrawal, or deletion
```

Every arrow is an interface. Every state transition needs provenance and a
claim class. No component may skip from candidate to truth or from generated
artifact to live behavior.

## Core invariants

1. **Authority before exposure:** authorization applies before IDs, counts,
   distances, snippets, caches, telemetry, graph neighborhoods, model input,
   export, or aggregation.
2. **Identity is explicit:** string or vector similarity cannot create task,
   project, fact, person, or collaborator identity.
3. **Time is multidimensional:** observed/source time, known/system time, valid
   time, release time, exposure time, and deletion time are distinct.
4. **Tool lifecycle is typed:** proposal, approval, dispatch, execution,
   result, durable side effect, terminal submission, refusal, retry, fallback,
   cancellation, and missingness are distinct.
5. **Projection loss is evidence:** ATIF, OTel, datasets, graphs, and rendered
   files carry loss receipts and never silently become canonical.
6. **Proposal is not release:** generated evals, memories, facts, skills, and
   collaboration candidates are inactive until reviewed.
7. **Influence changes evidence status:** traces exposed to an artifact are
   post-treatment and cannot independently validate that artifact.
8. **Deletion closes over derivatives:** candidates, releases, exposures,
   indexes, caches, telemetry references, exports, and rendered destinations
   need defined invalidation behavior.
9. **Repeated calls do not inflate N:** inference uses task/query and
   source/project clusters; deterministic repeats measure reliability.
10. **Credentials are a narrow hard exclusion:** authorized internal PII and
    classified content remain usable inside scope; reusable authentication
    material does not enter ordinary analysis planes.

## What works together

### Trace and evaluation block

```text
canonical DAG
  -> Signals selection
  -> AgentRx/OpenRCA hypothesis
  -> AgentEvals assertion proposal
  -> changed-system replay
```

This is a valid composition only if selection, diagnosis, assertion, and replay
outcomes remain separately scored.

### Memory block

```text
temporal evidence oracle
  -> Memory Palace / Graphiti-like representation
  -> deterministic / LangMem candidate extraction
  -> optional query-independent Dream proposal
  -> independent verification
  -> immutable release
  -> MEMORY.md or harness rendering
  -> controlled exposure and later utility
```

Graphiti, LangMem, Dreams, and Memory Palace can contribute different
mechanisms without becoming separate authorities.

### Skill block

```text
verified success/failure trajectories
  -> deterministic contrast / ReasoningBank / Trace2Skill
  -> optional GEPA / SkillOpt bounded search
  -> reviewed frozen procedure
  -> no-skill / placebo / expert / mined intervention
  -> sealed evaluator
```

NL2SQL is the best first domain because tool calls, database state, policy, SQL
attempts, and executable outcomes can be recorded.

### Similar-work and collaboration block

```text
authorized task signatures
  -> exact / structured / FTS / general dense / adapted dense
  -> human same-work labels
  -> anonymous reusable artifact
  -> reciprocal opt-in
  -> collaboration outcome
```

Similarity and collaboration are deliberately two different experiments.

## What does not work together

- Phoenix, Opik, and Langfuse should not all own datasets, evaluators,
  feedback, or deletion state.
- ATIF and OTel should not form competing canonical stores.
- Signals and embeddings should not be combined into a diagnosis label.
- A Graphiti group or graph edge should not be treated as authorization.
- LangMem or Dream output should not write directly to live memory.
- ReasoningBank or Hermes output should not mutate a live skill and then
  validate against influenced traces.
- A dense neighbor should not become a named collaborator.
- A failure count should not become a person skill label.
- Custom embeddings should not be trained before a reviewed hard slice exists.
- An external search/vector system should not be introduced before a frozen
  native workload failure.

## Resolving the main tensions

### Full factorial versus staged experiments

The v3 factorial primitive correctly supports eight independently switchable
mechanisms and a complete `2^k` lattice. That is a protocol and leakage-checking
capability, not a recommendation to immediately execute all 256 arms on sparse
public traces.

Resolution:

- run each mechanism alone first;
- validate construct, protocol, and outcome labels;
- run staged two-to-four-factor blocks with declared interactions;
- use the complete lattice only when sample size, costs, and identifiability
  make it credible.

This preserves K2/F1 interpretability while retaining F7's ability to model
interactions and G6's architecture comparisons.

### Simplicity versus systems thinking

B9 argues for one authority; F7 argues that the full feedback loop is
load-bearing. These are compatible. The system needs rich state transitions,
not many stateful products. One relational authority can represent candidates,
releases, exposures, outcomes, and influence without deploying every upstream
framework.

### Bayesian hypotheses versus socially risky output

B3 can rank uncertain hypotheses internally. H2 and I4 correctly block weak
person-level hypotheses from becoming manager-facing facts. Resolution:

- calibrated hypotheses may exist in private research and personal support;
- team/admin output remains artifact-first and contestable;
- named people, latent traits, and causal wording require a separate release
  standard or remain refused.

### Aurora-first versus architecture dogma

G6, B9, and current measurements support Aurora-first. L2 correctly warns that
this can become status-quo bias. Resolution: maintain explicit reversal gates
for selective-RLS recall and latency, deletion closure, failover, RDS Proxy,
connection headroom, analytics isolation, extension needs, and cost. If the
minimum architecture fails after bounded tuning, compare alternatives against
the same authority and deletion oracle.

## Enterprise question status

| Question | Current status | What changes the status |
|---|---|---|
| Show users all their history | Locally supported mechanics | Production imports, Aurora/load/failover, deletion, and capture-completeness gates |
| Find repeated friction and recovery | Candidate selection only | Human outcome/recovery labels and add/remove replay |
| Suggest evals | Proposal and mutation mechanics | Changed-system replay with benign-variation controls |
| Suggest memory / `MEMORY.md` | Proposal/release mechanics | Corrected temporal/dream exposure study with later utility |
| Find similar work | Conditional retrieval candidate | Human same-work labels on internal/project/time holdouts |
| Suggest collaboration | Unsupported | Artifact-first reciprocal opt-in trial with measured outcome |
| Identify missing cloud/domain skills | Unsupported as a trait | Confounder labels and prospective support interventions; person labels may remain prohibited |
| Recommend prompts/tools/skills/models | Causal hypothesis | Controlled exposure and independent task outcome |
| Train enterprise embeddings | Premature | Frozen hard-slice baseline failure and safe held-out lift |
| Leave Aurora | No evidence | Representative operations failure after bounded mitigations |

## Highest-information experiment order

1. Full cheap Signals replication with random and length baselines.
2. Human labels for informative traces, actual recovery, decisive steps,
   same-work task families, environmental blockers, and insufficient evidence.
3. Signals -> diagnosis -> eval -> changed-system replay.
4. Corrected latest versus temporal versus real released-Dream study.
5. NL2SQL protocol repair and family-disjoint procedure intervention.
6. Similar-work retrieval followed by artifact and reciprocal collaboration
   outcomes.
7. Support-opportunity taxonomy and intervention study.
8. Enterprise embedding adaptation only after a frozen retrieval hard slice.
9. Aurora operations gauntlet.
10. Relational versus Graphiti and native versus sidecar comparisons only on
    named failed slices.

## Architecture decision

Build or retain now:

- canonical full-fidelity model/tool trace DAG;
- personal history and exact search;
- typed task/attempt records;
- FTS and bounded general dense retrieval;
- deterministic selectors with random audit;
- proposal/review/release/exposure/outcome/influence tables;
- temporal facts and contradiction records;
- eval proposal and replay manifests;
- worker isolation and object payload references;
- claim classes and evidence receipts.

Research behind flags:

- AgentRx/OpenRCA diagnosis;
- AgentEvals changed-system replay;
- LangMem/Graphiti/Dream memory mechanisms;
- ReasoningBank/Trace2Skill/GEPA/SkillOpt procedure mechanisms;
- reciprocal collaboration;
- adapted embeddings;
- Frankensearch or other sidecars.

Do not build as current production features:

- automatic live memory or skill writes;
- a multi-product lifecycle stack;
- a graph or external vector authority;
- named vector-neighbor people search;
- employee skill, productivity, intent, loyalty, or performance inference;
- self-validated learning loops.

## Confidence

Overall synthesis confidence: **0.88** for the current claim ceiling and
one-authority proposal-first architecture.

Confidence is lower for the ultimate value of memory, procedure learning,
similar-work collaboration, enterprise embeddings, and Aurora sufficiency
because the decisive corrected experiments, internal labels, prospective
outcomes, and production operations runs do not yet exist.

The conclusion is intentionally reversible: a non-minimal component should be
promoted when it beats the minimal baseline on a frozen, independently labeled
or executable outcome under equal authority, deletion, provenance, latency,
cost, and rollback rules.
