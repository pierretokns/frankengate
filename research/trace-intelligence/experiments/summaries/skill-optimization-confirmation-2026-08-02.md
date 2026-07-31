# Skill optimization: what the trace evidence actually establishes

## Decision

We have **not** yet confirmed that Frankengate's trace-mined skills improve real task outcomes. We have now completed a real family-disjoint semantic intervention, but it was a negative result. We have confirmed that:

1. Outcome-conditioned traces can recommend a promising procedure offline.
2. A skill optimizer can run against a held-out split and reject bad edits.
3. Trace-derived protocol instructions can be executed through more than one local model/harness path.
4. On eight previously unused ALFWorld paths across four families, both Llama 3.2 and Qwen 3 4B achieved 0/8 wins for baseline and candidate. The candidate changed invalid-action rates in opposite directions by model but produced no success lift.
5. Replaying those identical eight paths through the second Ollama OpenAI-compatible harness produced the same Llama result: 0/8 wins for both arms and 66 candidate invalid actions versus 0 baseline.
6. A replayable rerun retained only environment actions and independently recomputed all 32 outcomes in fresh environments with zero mismatches.
7. The r13 control arm added a formatting placebo to the same eight-task cohort across both harnesses. No-skill, placebo, and trace-derived arms were all `0/8` on both harnesses; all 48 action sequences independently replayed with zero mismatches.

Those are prerequisites and a negative causal test, not evidence of a beneficial skill.

## Evidence

- MATM retrieval: successful-neighbor top-10 rate `0.747` vs `0.681` for all-trace neighbors, lift `+0.0665`, bootstrap 95% CI `[-0.0196, +0.1660]`. The model was **not rerun** with the retrieved procedure.
- GEPA: train/holdout optimizer plumbing executed; two mutations were rejected and the selected protocol skill did not improve the three-item holdout. The fixture measured terminal tool protocol, not semantic quality.
- The paired meta-analysis covers 23 protocol/semantic strata. It found no releasable semantic lift; the family-disjoint broker arm tied no-skill at `0/6`.

## Models and harnesses

We have exercised `llama3.2:latest` and `qwen3:4b` through an OpenAI-compatible native-tool path and an Ollama-native API path. This establishes protocol portability only. It is not yet a valid semantic comparison because the shared fixture has no domain task correctness oracle.

Microsoft SkillOpt's published v0.2.0 study is stronger external evidence: six real benchmarks, seven target models, and three harnesses with validation-gated gains. It validates the general method, not sufficiency of Frankengate traces.

## Required next gate

The sealed task-outcome recomputation gate now passes for this ALFWorld cohort, including the formatting placebo. The remaining gates are security/policy verification, a second-model control-arm replication, SkillOpt/SkillGen/RHO candidate arms, and a larger powered cohort; no skill should be promoted before those pass.

Machine-readable receipt: `experiments/results/skill-optimization-confirmation-2026-08-02.json`.
