# Skill-library and reusable-artifact prior art update

This update separates research that is close to Frankengate's trace-to-artifact
question from research that only shares the word “skill.” The papers below are
newer than the initial survey and are useful because several report both
positive transfer and failure cases.

## Closest matches

| Work | What it actually evaluates | What transfers to Frankengate | Hard edge |
|---|---|---|---|
| [SkillLearnBench](https://arxiv.org/abs/2604.20087), [code](https://github.com/cxcscmu/SkillLearnBench) | Continual skill generation on 20 verified tasks / 15 subdomains, with skill quality, trajectory, and task-outcome metrics | Three-level evaluation; repeated iterations with external feedback; explicit distinction between skill quality and task success | Public tasks are not private enterprise traces, governed SQL, or cross-user authorization; reported gains are not universal and stronger models do not always help |
| [SkillFlow](https://arxiv.org/abs/2604.17308), [task data](https://huggingface.co/datasets/zhang-ziao/SkillFlow-Task) | 166 tasks in 20 workflow families; lifelong skill discovery, repair, and reuse | Family-sequential protocol, negative-transfer measurement, skill-inflation and usage-vs-utility metrics | Workflow families are constructed and domain-agnostic; it does not mine raw OTel/.claude/.codex histories or execute governed SQL capsules |
| [SkillFoundry](https://arxiv.org/abs/2604.03964) | Converts heterogeneous scientific resources into executable, tested skill packages and iteratively expands/repairs/prunes a library | Operational contracts, environment assumptions, provenance, tests, and library maintenance | Resource mining is not user trace mining; no enterprise identity/scope/epoch or private alias collision problem |
| [MUSE-Autoskill](https://arxiv.org/abs/2605.27366) | Skill creation, reuse, refinement, unit tests, skill-level memory, and cross-agent transfer | Per-skill outcome history and test-before-store are directly applicable to reusable SQL/tool artifacts | SkillsBench evaluation is not a corporate trace corpus; memory is not an authority or deletion boundary |
| [AutoSkills](https://openreview.net/forum?id=rJS7Z3Oaw1) | Pre-builds/refines a hierarchical skill knowledge base from trajectories | Shared-library construction instead of each agent learning alone | Requires task/skill labels and does not solve corporate same-surface/different-system negatives |

## Important negative or qualifying evidence

SkillFlow reports a large gain for Claude Opus 4.6 (+8.43 points) but only a
small gain for Kimi K2.5 (+0.60), with regression for another model despite
high skill usage. SkillLearnBench likewise reports that no continual method
leads across all tasks/models and that self-feedback can drift while external
feedback helps. These findings are consistent with our native/proxy split and
our requirement for a neutral control, family/time holdout, and changed-system
replay.

## 2026 literature refresh

Three newer papers clarify the boundary between a reusable skill and a trace
summary:

| Work | Classification | Transferable idea | Hard edge for Frankengate |
|---|---|---|---|
| [SKILL-DISCO](https://arxiv.org/abs/2606.26669) | Adaptable, closest executable precedent | Treat repeated successful traces as parameterized control-flow subgraphs, then compile them into callable, executable, verifiable skills. It reports gains on ALFWorld and WebArena. | Its FSM-defined environments provide explicit transition structure and verification. Enterprise traces have hidden intent, authority epochs, schema/tool drift, and ambiguous aliases; the subgraph is not a semantic or authorization proof. |
| [Trace2Skill v5](https://arxiv.org/abs/2603.25158) | Adaptable, positive transfer claim | Parallel inductive consolidation of trajectories can produce portable procedures rather than a retrieval-only memory. The latest abstract reports transfer across model scales/families and OOD settings. | Our corrected car→broker and BIRD replays did not reproduce causal lift. The difference may be task-family continuity, verifier strength, model training, or trace quality; it is not a refutation. |
| [RESOURCE2SKILL](https://arxiv.org/abs/2606.29538) | Adjacent but valuable | Combine traces with tutorials, repositories, articles, code, visual examples, metadata, and provenance in a hierarchical Skill Wiki. The paper reports +11.9 points over no-skill across seven authoring domains. | Frankengate currently has mostly event traces and artifacts. The result does not show that raw corporate logs alone are sufficient, nor does it solve tenant scope, deletion, or changed-system replay. |
| [SoK: Agentic Skills](https://arxiv.org/abs/2602.20867) | Taxonomy/governance reference | Separates discovery, practice, distillation, storage, composition, evaluation, and update, and treats skills as governed executable dependencies with trust tiers. | It is a survey and security framing, not evidence that a particular mining or embedding strategy improves enterprise outcomes. |

The refresh changes the next experiment in one important way: skill candidates
should be represented in two layers. First, preserve an executable,
parameterized control-flow graph with preconditions, postconditions, and
verifiers. Second, preserve a semantic evidence packet with identifiers,
scope, temporal validity, provenance, and explicit unknown/NIL outcomes. The
first layer supports replay; the second protects against false semantic
transfer. Neither layer should be replaced by a free-form memory paragraph or
an embedding nearest neighbor.

## Exact Frankengate gap

None of these works combines all of the following:

1. raw multi-user enterprise traces;
2. exact identifier and alias discovery with same-surface wrong-system negatives;
3. governed SQL/tool artifact capsules carrying scope, authorization epoch,
   schema fingerprint, parameter contract, and expiry;
4. per-user/team/enterprise consent and deletion semantics; and
5. independent replay on a changed governed system before promotion.

That combination remains a credible research contribution. The contribution
should not be framed as “skills improve agents” in general. The defensible
claim is narrower: a governed trajectory-to-artifact lifecycle can measure
when a procedure transfers, when a near-neighbor is a hard negative, and when
the system must abstain.

## Revised experiment design

For every candidate artifact, record three separate outcomes:

* artifact quality: contract completeness, identifier grounding, tests, and
  independent reviewer agreement;
* retrieval quality: exact/lexical/structured, dense, and hybrid Recall@k/MRR
  on user/project/time-held-out positives and explicit hard negatives; and
* changed-agent utility: paired no-skill, length-matched neutral, and candidate
  replay on a fresh database/tool environment.

Promotion requires a preregistered lift on changed-agent utility, no security
or deletion regression, and a negative-transfer cohort. Skill usage or offline
similarity alone is not sufficient.
