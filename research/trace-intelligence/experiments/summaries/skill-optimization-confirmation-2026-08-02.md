# Skill optimization: what the trace evidence actually establishes

## Decision

We have **not** yet confirmed that Frankengate's trace-mined skills improve real task outcomes. We have confirmed only that:

1. Outcome-conditioned traces can recommend a promising procedure offline.
2. A skill optimizer can run against a held-out split and reject bad edits.
3. Trace-derived protocol instructions can be executed through more than one local model/harness path.

Those are prerequisites, not a causal skill-utility result.

## Evidence

- MATM retrieval: successful-neighbor top-10 rate `0.747` vs `0.681` for all-trace neighbors, lift `+0.0665`, bootstrap 95% CI `[-0.0196, +0.1660]`. The model was **not rerun** with the retrieved procedure.
- GEPA: train/holdout optimizer plumbing executed; two mutations were rejected and the selected protocol skill did not improve the three-item holdout. The fixture measured terminal tool protocol, not semantic quality.
- The paired meta-analysis covers 23 protocol/semantic strata. It found no releasable semantic lift; the family-disjoint broker arm tied no-skill at `0/6`.

## Models and harnesses

We have exercised `llama3.2:latest` and `qwen3:4b` through an OpenAI-compatible native-tool path and an Ollama-native API path. This establishes protocol portability only. It is not yet a valid semantic comparison because the shared fixture has no domain task correctness oracle.

Microsoft SkillOpt's published v0.2.0 study is stronger external evidence: six real benchmarks, seven target models, and three harnesses with validation-gated gains. It validates the general method, not sufficiency of Frankengate traces.

## Required next gate

Run the same trace-derived candidate and no-skill baseline on family-disjoint held-out tasks, with at least two models and two harnesses, sealed task outcomes, an independent correctness/security verifier, and explicit tool-budget/abstention accounting. No skill should be promoted before that gate passes.

Machine-readable receipt: `experiments/results/skill-optimization-confirmation-2026-08-02.json`.
