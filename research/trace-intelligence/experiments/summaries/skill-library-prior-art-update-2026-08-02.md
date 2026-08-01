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
