# “Jeopard” Identity Resolution: GEPA/gskill and Frankengate Integration

**Date:** 2026-07-30
**Decision:** operationally resolve the requested “Jeopard” self-improving
agent/skill system to **GEPA/gskill**, while retaining a small, explicit residual
ambiguity. Do not treat Meta JEPA or literal Jeopardy repositories as equivalent.

## Executive result

The strongest evidence is not phonetic guesswork. An official AI Engineer talk
is titled **“Agent Optimization with Pydantic AI: GEPA, Evals, Feedback
Loops.”** Its captured captions repeatedly render the spoken project name as
“Jeppa,” “Jeppo,” “Jepa,” and, at 35:03, 35:37, and 36:08, **“Jeopardy.”** The
surrounding material describes GEPA-specific adapters, reflection, candidate
prompts, evaluation batches, and a Pareto frontier. This directly explains how
“Jeopard” entered the conversation.

The intended system is therefore GEPA with high confidence. The relevant
skill-learning implementation is its `gskill` subproject:

1. generate repository-grounded executable tasks with SWE-smith;
2. run an agent and retain its trajectory, patch, and test feedback;
3. let GEPA propose mutations to a textual `skills` component;
4. select candidates on validation tasks;
5. test the selected skill on held-out tasks; and
6. project `best_skills.txt` into an agent system prompt or a harness
   `SKILL.md`.

This is useful to Frankengate, but it is **not** a trace database, memory system,
independent evaluator, governed release service, or evidence authority. GEPA
should be an optional candidate-search worker behind Frankengate’s immutable
trace, evaluation, authorization, and release boundaries.

## Identity evidence and residual ambiguity

### Evidence chain

| Evidence | Observation | Weight |
|---|---|---:|
| [Official AI Engineer talk](https://www.youtube.com/watch?v=A48uhxfxbsM) | The title names GEPA; the captions render the same spoken name as “Jeppa,” “Jeppo,” “Jepa,” and “Jeopardy.” The “Jeopardy” passages discuss GEPA’s progress display, proposer input, and Logfire instrumentation. | Decisive |
| [Official Pydantic article](https://pydantic.dev/articles/prompt-optimization-with-gepa) | Describes the same Pydantic Evals + GEPA adapter, reflection, proposal, acceptance, Pareto selection, and OTel/Logfire workflow demonstrated in the talk. | Strong corroboration |
| [GEPA repository, `v0.1.4`](https://github.com/gepa-ai/gepa/tree/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975) | Contains the adapter, reflective proposer, Pareto engine, persistent run state, and `gskill` executable skill-learning pipeline that match the user’s requested mechanism. | Strong corroboration |
| Literal GitHub searches | Searches for `jeopard agent skills`, `jeopard self evolving agent`, and `JEPA agent optimizer` found no matching self-improving skill system. | Negative evidence |

The local transcript is retained in the State of AI source corpus. Its content
is not copied into the experiment manifest; only its source ID and SHA-256 are
recorded.

### Ranked ambiguity report

| Rank | Candidate | Confidence | Disposition | Falsifier |
|---:|---|---:|---|---|
| 1 | [GEPA/gskill](https://github.com/gepa-ai/gepa/tree/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/gskill) | 0.97 | Operational identity | A primary source naming a distinct “Jeopard” agent-skill system, or user confirmation that a different author/repository was intended |
| 2 | A private or unindexed system named Jeopard | 0.02 | Residual unknown | Repository, paper, author, talk, or package identity |
| 3 | [Meta JEPA](https://github.com/facebookresearch/jepa/tree/51c59d518fc63c08464af6de585f78ac0c7ed4d5) | 0.009 | Ruled out by mechanism | Evidence of an official trace-to-skill learning loop; the reviewed repository is self-supervised visual representation learning |
| 4 | [`banka-lecho/JeopardyAgent`](https://github.com/banka-lecho/JeopardyAgent/tree/e4d425cdd6abed40b1317a2697aa762f6badf691) or [`ashishthomas2202/Jeopardy-Agent`](https://github.com/ashishthomas2202/Jeopardy-Agent/tree/821de01552f903ef848e9e52c0e634260067eb28) | 0.001 | Ruled out | A hidden trace-learning implementation; the reviewed repositories are respectively an MLE template and an unrelated voice/customer-service agent |

## Pinned source research

### GEPA

- **Repository:** [gepa-ai/gepa](https://github.com/gepa-ai/gepa)
- **Latest stable release reviewed:** [`v0.1.4`](https://github.com/gepa-ai/gepa/releases/tag/v0.1.4)
- **Commit:** [`8b0ce6cd99a234f6b74daf37558a2ac0ce18f975`](https://github.com/gepa-ai/gepa/tree/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975)
- **Release date:** 2026-07-15
- **Paper:** [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning](https://arxiv.org/abs/2507.19457)
- **Relevant implementation:** [`src/gepa/gskill`](https://github.com/gepa-ai/gepa/tree/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/gskill)
- **Upstream dataset used by gskill:** [`SWE-bench/SWE-smith` at `ea6d7173829c7ec8fa16c22055699ff2e9188091`](https://huggingface.co/datasets/SWE-bench/SWE-smith/tree/ea6d7173829c7ec8fa16c22055699ff2e9188091)

The GEPA tag points directly to the reviewed commit. The SWE-smith revision is
our audit pin. Upstream gskill calls `load_dataset("SWE-bench/SWE-smith",
split="train")` **without** a revision, so a vanilla rerun does not enforce that
pin. Frankengate experiments must supply and record the dataset revision.

### Environment and invocation surface

The pinned gskill runner is Python-based, uses Hugging Face `datasets`, invokes
mini-SWE-agent with a configurable model (default `gpt-5-mini`), and verifies
patches in Docker through SWE-smith. It exposes repository, train/validation/test
sizes, seed, worker count, model, run directory, and evaluation-budget controls.
The run directory is resumable through `gepa_state.bin`.

For a reproducible Frankengate run, the wrapper must additionally freeze:

- GEPA, gskill, mini-SWE-agent, SWE-smith, Docker image, repository, base commit,
  tool harness, model, and evaluator revisions;
- exact task IDs and family/project-disjoint split membership;
- model parameters, prompt/skill bytes, environment variables by **name only**,
  and dependency lock digest;
- network policy, timeouts, resource limits, retry policy, and random seeds; and
- an immutable mapping from every evaluation result to trace/span IDs and
  authorization scope.

Do not store credentials in the manifest. A runnable environment should refer to
secret names and credential classes, never values.

### Source-level gotchas

1. The dataset load is unpinned.
2. GEPA state is Python pickle (`gepa_state.bin`), which is unsuitable as an
   untrusted interchange or enterprise authority record.
3. Adapter trajectories are deliberately opaque to GEPA. Schema quality,
   tool-call completeness, scope metadata, and provenance remain the adapter’s
   responsibility.
4. Individual execution failures are expected to become scored results rather
   than exceptions. A permissive adapter can therefore hide systemic harness
   failures as ordinary zero scores unless Frankengate classifies infrastructure
   failures separately.
5. gskill’s default score is binary executable-test success. That is stronger
   than an LLM preference score, but it does not measure security, authorization,
   cost, latency, operator usability, or out-of-domain regressions.
6. GEPA compares minibatch score sums and tracks validation means/Pareto fronts.
   Mixing incomparable score scales or mutable evaluator versions invalidates
   selection.
7. The upstream experiment logger includes proposer inputs, traces, prompts,
   task metrics, and summaries in ordinary local JSON/JSONL files. Those files
   do not implement RLS, append-only integrity, retention policy, or release
   authorization.
8. The code supports train/validation/test splits, but a split by shuffled row is
   not enough for enterprise traces. Related tasks, repositories, users, issue
   templates, or repeated work episodes can leak across splits.

## Exact mechanism

GEPA represents an optimizable system as a dictionary of named textual
components. Its [adapter contract](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/core/adapter.py#L16-L216)
requires an evaluator to run a candidate over examples and return outputs,
per-example scores, and optional rich trajectories. The adapter then converts
those trajectories into a small JSON-serializable reflective dataset. A
[reflective proposer](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/proposer/reflective_mutation/reflective_mutation.py#L43-L161)
uses that feedback to propose component mutations.

The engine evaluates a candidate mutation on a minibatch, rejects non-improving
proposals, evaluates accepted proposals on the validation set, and maintains
Pareto frontiers across examples and optionally objectives. It may merge
complementary candidates. The search is budgeted and resumable. This is
reflective, evidence-conditioned textual optimization—not gradient training of
the underlying model.

`gskill` instantiates that abstraction as follows:

| Stage | gskill behavior | Frankengate interpretation |
|---|---|---|
| Task production | SWE-smith mines real repository commits and builds verifiable Docker tasks | A task/environment generator, not a source of enterprise truth |
| Rollout | mini-SWE-agent receives the task plus current `skills` text | A controlled replay with a candidate artifact |
| Trace | Agent trajectory, patch, step/token estimates, and test output are retained as reflection side information | Evidence input; convert to canonical trace/span/event references rather than flattening |
| Evaluation | Apply patch, run FAIL_TO_PASS, then PASS_TO_PASS tests; return 1 or 0 | Deterministic task outcome, but incomplete policy score |
| Proposal | Reflection model receives selected trajectory/test feedback and edits the `skills` text | Untrusted candidate generator |
| Selection | GEPA accepts improvements and maintains a validation Pareto frontier | Search/selection aid, not release approval |
| Held-out check | Runner can evaluate the selected skill on a separate test set | Required but must become family/project-disjoint, immutable, and independently operated |
| Projection | Save `best_skills.txt`; optionally install as `.claude/skills/<repo>/SKILL.md` | Only publish an approved Frankengate release projection |

The [gskill fitness function](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/gskill/gskill/swe_fitness_fn.py#L15-L209)
captures the full agent trace and test evidence for reflection. The
[split and test code](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/gskill/gskill/train_optimize_anything.py#L381-L452)
uses seeded train/validation/test partitions, and the
[post-optimization path](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/gskill/gskill/train_optimize_anything.py#L730-L807)
writes `best_skills.txt` and optionally evaluates it on the test set.

## What GEPA stores—and what it does not

GEPA’s
[`GEPAState`](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/core/state.py#L142-L346)
stores:

- candidate texts and parent-candidate IDs;
- per-validation-example and per-objective scores;
- instance, objective, and Cartesian Pareto frontiers;
- evaluation counts and discovery accounting;
- a full program-level optimization trace;
- optional best outputs and evaluation cache; and
- opaque adapter state.

When a run directory is configured it writes `gepa_state.bin`,
`run_log.json`, and `candidates.json`. gskill additionally writes
`iterations.jsonl`, `proposer_inputs.jsonl`, prompt versions, configuration,
summary, test results, and `best_skills.txt`.

It does **not** natively store:

- canonical OTel/OpenInference/ATIF trajectories;
- tool calls as queryable typed events;
- user, team, enterprise, classification, or authorization-epoch scope;
- immutable source-event lineage;
- RLS policy or field/chunk classification;
- independent evaluator identity and attestation;
- candidate review, approval, release, withdrawal, or rollback authority; or
- artifact exposure and downstream influence records.

Frankengate should retain normalized evidence in its governed trace store and
give GEPA only a scoped, content-minimized experiment view. GEPA’s local run
directory is a cache/checkpoint, not the system of record.

## Evaluator separation

GEPA separates roles at the API level:

- the **adapter/evaluator** executes candidates and produces scores and traces;
- the **reflection/proposer model** receives a reflective dataset and proposes
  text; and
- the **engine** applies acceptance and Pareto selection.

That is useful logical separation, but it is not independence. All three can run
in one process; the adapter defines both evidence and score; the proposer may
see evaluator details; the same task family may appear across splits; and local
files can be rewritten. The optimizer can exploit an evaluator blind spot just
as any optimizer can.

Frankengate needs four separate authorities:

1. **Proposer:** may read an explicitly authorized evidence projection and
   create candidate artifacts.
2. **Replay runner:** executes a frozen candidate in a pinned environment and
   cannot change evaluator definitions.
3. **Evaluator:** scores immutable replay outputs against hidden/frozen checks;
   its identity, version, and inputs are attested.
4. **Release controller:** applies policy, minimum per-family floors, security
   vetoes, human review where required, and signed publication/withdrawal.

The proposer must never receive hidden test labels, and a release controller
must not accept GEPA’s `best_candidate` merely because it won the optimizer’s
validation frontier.

## Empirical evidence and its limits

### GEPA paper

The GEPA paper reports results across six tasks: an average improvement of more
than six percent over GRPO, gains up to twenty percent, up to thirty-five times
fewer rollouts, and more than ten percent average improvement over MIPROv2.
These are author-reported benchmark results for reflective prompt evolution.
They establish that the search algorithm is serious; they do not establish
enterprise trace-derived skill promotion.

### gskill

The [official gskill report](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/docs/docs/blog/posts/2026-02-18-automatically-learning-skills-for-coding-agents/index.md#L31-L145)
reports roughly 300 SWE-smith tasks per repository and fewer than 300 rollouts:

| Harness/model | Repository | Baseline | GEPA skill | Delta |
|---|---|---:|---:|---:|
| mini-SWE-agent / GPT-5-mini | Jinja | 55% | 82% | +27 pp |
| mini-SWE-agent / GPT-5-mini | Bleve | 24% | 93% | +69 pp |

The same report claims cross-harness transfer to Claude Code. Its prose and
figures are internally inconsistent:

- Bleve/Haiku prose says 79.3% to 100%, while the plotted caption says 79.3% to
  98.3%.
- Jinja/Haiku prose says 93.9% to 98.5%, while the plotted caption says 93.9% to
  100%; 98.5% is the plotted Sonnet-with-skill value.

Use the plot captions as the more specific evidence record, but label both as
author-reported. The report does not show independent replication, multiple
random seeds, confidence intervals, or a family-disjoint enterprise trace
evaluation. It also notes that SWE-smith tasks are simpler and that some learned
skills are specific to SWE-smith-style issue fixing.

### Pydantic example

The official Pydantic integration reports an illustrative contact-extraction
validation score increasing from 86.88% to 96.88%. It is useful evidence for the
adapter boundary and OTel observability, not for generalization at enterprise
scale.

## Comparison with the already reviewed systems

| System | Primary contribution | Trace/log behavior | Learning/update loop | Evaluator separation | What Frankengate should take |
|---|---|---|---|---|---|
| [GEPA/gskill `8b0ce6c`](https://github.com/gepa-ai/gepa/tree/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975) | Budgeted reflective text search, per-example Pareto selection, executable coding-task fitness | Opaque adapter trajectories plus local pickle/JSON/JSONL run logs | Reflect → mutate text → minibatch accept → validation frontier → optional held-out test | Logical adapter/proposer split, no process or release independence | Optional bounded mutation/search over evidence-linked candidates |
| [Trace2Skill `3d0b52a`](https://github.com/Qwen-Applications/Trace2Skill/tree/3d0b52a140f002a512930252b613c49048f7d5ac) | Parallel failure analysis, trajectory-local patches, hierarchical loss-aware merge | Consumes pooled trajectories and emits proposed skill patches | Analyze shards → patch locally → merge → application/format checks | Proposal and validation remain close; requires external hidden replay | Evidence-backed pooled proposal generation |
| [ReasoningBank `ed80611`](https://github.com/google-research/reasoning-bank/tree/ed80611788292ea739f1effd31f16c53823b8a0d) | Induces reusable lessons from both successes and failures and retrieves by task similarity | Benchmark trajectories become a retrievable lesson bank | Outcome-conditioned induction → retrieval on later task | Self-evaluation/retrieval contamination is possible; no governed release | Candidate lessons with exact source/outcome links, evaluated outside the bank |
| [Hermes Agent `3ef6bbd`](https://github.com/NousResearch/hermes-agent/tree/3ef6bbd201263d354fd83ec55b3c306ded2eb72a) | Runtime memory/skill projection, provenance, protected writes, snapshots, curation, rollback | Session history and live files are operational state | Background review can update memory/skill files | Reviewer/tool restrictions exist; outcome validation remains insufficient | Protected projections, provenance, backup, withdrawal and rollback patterns |
| [Hermes Self-Evolution `0a929e3`](https://github.com/NousResearch/hermes-agent-self-evolution/tree/0a929e3aa20e15cf04dc7c28492a7d41a5139125) | Intended GEPA/MIPRO skill-optimization scaffold | Examples, generated Markdown and metrics | Intended evolve/evaluate loop | Reviewed implementation does not mutate the claimed skill body and uses weak keyword-overlap fitness | Do not use as an empirical baseline at this pin |

### What composes well

1. **Trace2Skill-style pooled contrast** or **ReasoningBank-style
   success/failure induction** creates evidence-linked candidate lessons.
2. **GEPA** optionally explores bounded textual variants or combinations of
   those candidates.
3. A **separate immutable replay/evaluator service** tests candidates on hidden,
   family-disjoint tasks and policy checks.
4. **Frankengate governance** records scope, authorization epoch, provenance,
   approval, signed release, exposure, influence, withdrawal, and rollback.
5. **Hermes-style projections** materialize only an approved release into
   `SKILL.md`, `MEMORY.md`, or the equivalent harness artifact.

### Hard edges and combinations that should not be built

- Do not run Hermes reflection, ReasoningBank append, Trace2Skill merge, and
  GEPA mutation as concurrent writers to a live skill. Attribution and rollback
  become non-reproducible.
- Do not flatten tool calls and typed span events into reflection text and then
  discard the original trace graph. Structural queries and evidence lineage
  would be lost.
- Do not let a memory-retrieval system fetch the candidate lesson being tested,
  related traces from the hidden family, or post-outcome information.
- Do not use GEPA’s local files or Pareto frontier as release authority.
- Do not equate executable repository tests with enterprise policy correctness.
- Do not infer “the user improved” from aggregate score movement without
  separating task mix, model/harness version, assistance exposure, and repeated
  attempt effects.

## Falsifiable Frankengate protocol

### Research question

Does evidence-conditioned skill evolution improve independently verified
enterprise-task outcomes beyond retrieval, placebo text, and simpler frozen
lessons, without authorization leakage, safety regression, or unacceptable
cost/latency?

### Experimental arms

| Arm | Artifact supplied to the frozen agent |
|---|---|
| A0 | No learned skill |
| A1 | Placebo skill matched for length, format, and retrieval path |
| A2 | Frozen Trace2Skill-style pooled success/failure proposal |
| A3 | Frozen ReasoningBank-style outcome-conditioned lessons |
| A4 | GEPA mutation/selection over the bounded A2/A3 candidate frontier |
| A5 | Human-authored expert skill |
| A6 | Optional direct single-trace reflection negative control |

The same candidate cannot be generated from or evaluated on its own hidden task
family. Splits must be disjoint by user/work episode, task template, repository
or data domain, and source lineage—not merely row ID.

### Required trace representation

Each rollout must preserve:

- trace, session, request, span, parent-span, and ordered event IDs;
- user/team/enterprise scope and authorization-epoch reference;
- model, provider, prompt, skill, tool schema, and harness revisions;
- complete tool call/request/result/error relationships, including retries;
- timestamps, cost, latency, token use, outcome labels, evaluator identities,
  and policy decisions;
- source task family, environment/container digest, candidate/release ID, and
  exposure assignment; and
- classifications on source text, tool payloads, derived chunks, embeddings,
  lessons, and released artifacts.

GEPA receives only authorized experiment views. It may refer back to evidence by
immutable IDs, but it must not become the durable evidence store.

### Evaluation and statistics

- Freeze model, tools, environment, evaluator, task assignment, and budgets
  before revealing hidden outcomes.
- Run multiple seeds and paired tasks where feasible.
- Estimate outcome deltas with paired bootstrap intervals or cluster-robust
  inference by task family/user/work episode.
- Report overall and per-family success, correct-to-incorrect regressions,
  retries, tool errors, cost, latency, and skill-use influence.
- Evaluate one-shot transfer, repeated-attempt recovery, and retention on
  future tasks separately.
- Run evaluator-blind-spot, prompt-injection, unauthorized-scope retrieval,
  stale-authorization-epoch, and adversarial tool-output tests.

### Promotion gates

A4 is eligible for release only if it:

1. beats A0 and A1 on independently verified hidden success with a predeclared
   minimum effect;
2. does not underperform A2, A3, or A5 beyond declared uncertainty where those
   are the relevant simpler baseline;
3. clears every per-family performance floor;
4. produces no security, RLS, classification, or cross-scope leakage;
5. stays within cost and latency budgets;
6. passes a manual evidence review for unsupported or overgeneralized claims;
7. has complete provenance from source traces through candidate and evaluation
   to release; and
8. can be withdrawn and every exposed use traced to its release ID.

Any security/RLS failure is a hard veto, not an objective traded on a Pareto
frontier.

### What would disprove the integration thesis

The GEPA arm should be removed from the production architecture if:

- A4 does not reliably beat A2/A3 or the placebo after repeated,
  family-disjoint experiments;
- gains disappear when evaluator and proposer are separated;
- improvements are confined to SWE-smith-like or otherwise synthetic task
  templates;
- candidate search cost exceeds the value of the measured gain;
- the optimizer repeatedly exploits evaluator blind spots;
- learned text cannot be attributed to evidence or safely classified; or
- simpler exact retrieval or human-authored skills achieve equivalent outcomes.

## Architectural decision

No database migration is justified by GEPA itself. GEPA needs a small,
JSON-serializable reflective view and a checkpoint directory; it does not
benefit directly from replacing PostgreSQL/Aurora with a specialized vector
store. The hard requirements are canonical tool-inclusive trace storage,
structured metadata queries, scoped evidence retrieval, immutable experiment
manifests, and independent replay/evaluation. Those should remain database and
service decisions made against Frankengate’s full trace-mining workload, not
against the optimizer’s local state format.

Adopt:

- GEPA/gskill as a pinned **experimental candidate-search arm**;
- gskill’s executable verification and explicit held-out test stage;
- adapter-generated actionable side information linked to original trace IDs;
- per-example/per-objective frontier analysis for research; and
- the falsifiable multi-arm protocol above.

Do not adopt:

- unpinned Hugging Face loads;
- pickle/JSONL as the enterprise source of truth;
- optimizer-selected candidates as automatically releasable skills;
- row-random splits for related enterprise work;
- direct mutation of shared harness memory/skill files; or
- the assumption that a better prompt score proves a durable human skill gap or
  a safe enterprise-wide recommendation.

## Primary sources

- [GEPA `v0.1.4` source](https://github.com/gepa-ai/gepa/tree/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975)
- [GEPA paper](https://arxiv.org/abs/2507.19457)
- [GEPA adapter contract](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/core/adapter.py#L16-L216)
- [GEPA engine](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/core/engine.py#L439-L889)
- [GEPA persistent state](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/core/state.py#L142-L346)
- [gskill README](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/gskill/README.md)
- [gskill fitness implementation](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/gskill/gskill/swe_fitness_fn.py#L15-L209)
- [gskill experiment report](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/docs/docs/blog/posts/2026-02-18-automatically-learning-skills-for-coding-agents/index.md#L31-L145)
- [Pydantic GEPA + Evals article](https://pydantic.dev/articles/prompt-optimization-with-gepa)
- [Official AI Engineer talk](https://www.youtube.com/watch?v=A48uhxfxbsM)
- [Hugging Face DSPy/GEPA cookbook](https://huggingface.co/learn/cookbook/dspy_gepa) — useful ecosystem example; not identity authority, and its expansion of the acronym conflicts with the canonical Genetic-Pareto name
- [SWE-smith dataset audit pin](https://huggingface.co/datasets/SWE-bench/SWE-smith/tree/ea6d7173829c7ec8fa16c22055699ff2e9188091)
- [Meta JEPA ruled-out source](https://github.com/facebookresearch/jepa/tree/51c59d518fc63c08464af6de585f78ac0c7ed4d5)
