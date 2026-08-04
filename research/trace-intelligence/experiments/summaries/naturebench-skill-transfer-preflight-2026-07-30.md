# NatureBench natural-trace skill-transfer preflight

This is the first bounded inventory of natural agent trajectories used to
prepare the requested skill-transfer experiment. It covers ten paper/task
families and five source arms: Claude Code with DeepSeek V4 Pro, GLM 5.1, and
Opus 4.7; Codex with GPT-5.5; and Gemini CLI with Gemini 3.5 Flash. The source
revision is pinned in
[`configs/datasets/naturebench-skill-transfer-v1-2026.json`](../../configs/datasets/naturebench-skill-transfer-v1-2026.json).

| Source arm | Successful historical runs | Timeouts | Historical success rate |
| --- | ---: | ---: | ---: |
| Claude Code / DeepSeek V4 Pro | 4/10 | 6 | 0.40 |
| Claude Code / GLM 5.1 | 1/10 | 9 | 0.10 |
| Claude Code / Opus 4.7 | 8/10 | 2 | 0.80 |
| Codex / GPT-5.5 | 8/10 | 2 | 0.80 |
| Gemini CLI / Gemini 3.5 Flash | 10/10 | 0 | 1.00 |

The matrix confirms that the corpus contains genuinely different harness/model
arms and enough task families for a family-disjoint split. It also shows why a
historical success rate cannot be called a skill effect: model and harness are
already large uncontrolled factors.

## What this confirms

- We have a concrete natural-trace source with tool-rich transcripts and
  independent per-run status/judge files.
- The same task families were attempted by multiple models and harnesses, so a
  future skill can be trained on one family/model and tested on another.
- The source runs expose a candidate procedural prior (inspect task/data,
  establish a resource/evaluation baseline, train with validation, verify the
  artifact) that can be mined deterministically from transcripts.

## What this does not confirm

No candidate skill was injected into a replay, and no no-skill/placebo/expert
counterfactual was run on these tasks. Therefore this preflight does **not**
confirm that Frankengate traces optimize skills, improve a model, or transfer
across harnesses. The result is an availability and baseline receipt, not a
causal performance result.

The decisive next run is the bead
`bif-kyy.17.13.4.4.5.3.2`: use a family-disjoint natural cohort, generate a
candidate from training traces, and execute no-skill, placebo, mined,
SkillOpt/SkillGen/RHO arms across at least two model classes and two harnesses.
Score paired repairs and regressions with an independent verifier, report
cost/latency, and reject or roll back candidates that do not beat the controls.

Raw transcripts remain in disposable storage; the committed receipt contains
only hashes, statuses, and aggregates.
