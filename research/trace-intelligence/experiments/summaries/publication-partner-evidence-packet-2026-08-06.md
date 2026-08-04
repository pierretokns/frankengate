# Publication/partner evidence packet (2026-08-06)

This packet updates the partner strategy with the latest empirical results. It
is a methods-reproduction proposal, not a claim that any group has agreed to
collaborate.

## The contribution we can defend now

**Governed trajectory-to-artifact learning with explicit refusal.** A trace
system should preserve structured identifiers, scope, temporal authority,
parameterized SQL/tool templates, provenance, and independent replay outcomes.
It should use dense/model retrieval only to generate candidates inside a
compatible structural set; if no compatible template exists, it should abstain
or regenerate rather than reuse the nearest wording.

Evidence already measured:

- governed capsules fail closed on stale authority, wrong scope, expiry,
  schema drift, parameter mismatch, and unsafe interpolation;
- whole-query natural artifact retrieval is a `0/10` library-coverage null;
- parameterized-template retrieval recovers `52/52` known mutations, while a
  strict template gate abstains on `10/10` template-absence NIL proxies;
- structured identifiers beat the tested dense adapter on collision safety;
- Trace Commons workstream-proxy retrieval reached prompt `13/13` and durable
  identifier `12/13` same-project top-1, while event structure was `1/13`;
  this is candidate-discovery evidence only because the cohort has no stable
  principal or outcome labels;
- A leave-one-project-out token-weight adapter tied its baseline at `13/13`
  top-1 and MRR `1.0`, demonstrating that this public proxy is too easy to
  measure domain-adaptation lift rather than proving adaptation unnecessary;
- BIRD-SQL trace-mined procedure replay reached `8/40`, equal to no-skill and
  below the formatting placebo on latency, so no skill was promoted;
- BIRD-Interact provides 600 ambiguity/follow-up tasks, while its 20 public
  ADK samples expose the trajectory/reward schema but are not a benchmark.
- FinanceBench provides a clean systems-side result: a pinned finance model
  reached Recall@20 `1.0` / MRR `.8087`, while a different loopback serving path
  using Nomic reached `.4533/.1661` on the same projection. Governed pgvector
  query latency was p50 `2.02ms` / p95 `2.96ms`. This supports treating model
  snapshot, prefix, dimension, serving path, and rebuild lineage as part of the
  retrieval artifact—not as deployment trivia.

The leading positive hypothesis is now **validated subplan composition**, not
generic memory or one-shot procedural skill transfer. Two independent
family-disjoint BIRD replays used the same 16-example source-family library:
the composed arm achieved `8/40` exact outcomes versus `6/40` for both no-skill
and formatting placebo. The stable task comparison was one win and zero losses,
so this is repeatable but low-headroom and underpowered. The same cohort's
one-shot trace-mined procedure was equal to no-skill and slower.

These are bounded mechanics and negative/diagnostic results, not proof that a
generic memory layer improves agents.

## Partner fit

| Partner | Exact question to study | What we bring | What they add |
|---|---|---|---|
| CMU LTI / SkillLearnBench | Does reviewed or generated procedural guidance improve changed SQL/tool tasks under task-family holdouts? | Frozen artifact capsules, parameterized-template gate, no-skill/placebo/reviewed/generated arms, independent verifiers. | Continual-learning benchmark design, skill-quality/trajectory-quality separation, task-disjoint methodology. |
| MIT DSAIL | What is the smallest database architecture for governed artifact retrieval under schema drift, RLS, deletion, and latency constraints? | PostgreSQL/SQLite capsule contract, identifier/hard-negative receipts, changed-system fixtures, planner measurements. | Learned-data-system and query-workload expertise; scale and systems evaluation. |
| Harvard CHARM / Variation Lab | Do trace-derived suggestions improve the user’s next task or only retrieval metrics? | Review-only suggestion pipeline, explicit NIL/unclear outcomes, friction/clarification cohort, opt-in UX protocol. | Human learning, agency, sensemaking, and prospective user-outcome study design. |
| MIT CLEAR / TRAC | How should uncertainty, abstention, provenance, deletion, and negative transfer govern skill release? | Evidence chain, audit receipts, rollback gate, authorization boundaries, changed-system safety cases. | Accountability, robustness, intelligibility, and human-agent learning methodology. |
| Harvard DASlab | How should traces, artifacts, indexes, and repeated workloads be stored and queried efficiently? | Workload fixtures, parameterized templates, latency/cost measurements, deletion/RLS requirements. | Data-management and adaptive-indexing expertise. |

## First joint study

Use a sealed 20–40-task SQL/tool cohort with two or more task families and a
changed-system split. Pre-register:

1. no artifact;
2. exact/structured retrieval;
3. dense candidate retrieval;
4. reviewed parameterized artifact;
5. reviewed typed-subplan composition;
6. generated/prose procedure (negative control); and
7. frontier regeneration when the compatibility set is empty.

Measure semantic outcome, wrong-system-before-target, authority/deletion safety,
abstention, reviewer agreement, tool calls, latency, and cost. Separately run
the BIRD-Interact clarification cohort with no-procedure, clarification,
over-questioning placebo, and regeneration arms once the evaluator/test bundle
is available. Do not merge the two datasets into one statistical estimate.

The composition arm should be evaluated on at least four database families,
two source-library variants, irrelevant-library/NIL tasks, one schema-change
family, and repeated frontier seeds. A paper should report library granularity,
source/target splits, and stable task wins rather than treating repeated seeds
as independent samples.

## Publication lanes

- **SIGIR/ACL Industry:** identifier-aware retrieval, hard negatives,
  parameterized artifacts, and explicit NIL refusal.
- **SIGMOD/MLSys:** governed artifact storage, schema drift, RLS/deletion, and
  replay/latency tradeoffs.
- **CHI/CSCW:** friction suggestions, clarification, skill-gap explanations,
  and prospective human outcomes.

The first paper should stay within one lane. A broad “enterprise memory” claim
would exceed the current evidence.

## Outreach package

Provide the research branch, manifests, content-free receipts, deterministic
verifiers, and a sealed replay API. Keep employee traces and hidden evaluator
data outside the repository. Ask partners for methods review and independent
reproduction, not access to raw enterprise logs.
