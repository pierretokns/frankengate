# Skill-optimization evidence checkpoint (2026-08-01)

## Decision

We have **not confirmed that skills mined from traces improve task
performance**. We have confirmed that a trace-derived procedure can be
constructed, exposed to real model tool loops, and measured under a governed
runner. The observed effects are model- and harness-sensitive, including
negative effects, so no mined skill is eligible for automatic promotion.

## What has actually been tested

| Evidence | Model/harness | Arms | Result | Interpretation |
| --- | --- | --- | --- | --- |
| Natural-trace candidate transfer preflight | Historical NatureBench arms | no injected intervention | 4/10, 1/10, 8/10, 8/10, 10/10 depending on historical arm | Candidate extraction only; historical arms cannot identify a causal skill effect |
| Synthetic native-tool intervention | Llama 3.2 via OpenAI-compatible API | no-skill, formatting placebo, trace-mined | 3/6 terminal matches for every arm | No lift; protocol sensitivity was not observed on this model/fixture |
| Synthetic native-tool intervention | Qwen 3 4B via OpenAI-compatible API | same three arms | no-skill 6/6, placebo 0/6, trace-mined 3/6 | Strong model sensitivity; the mined candidate was harmful relative to baseline on this slice |
| Cross-harness control | Llama 3.2 via OpenAI-compatible and Ollama-native APIs | same three arms | 3/6 for every arm in both harnesses | Harness swap did not create a skill lift; behavior was reproducible at the protocol level |
| Governed visible SQL pilot | Llama 3.2, constrained PostgreSQL, car-dealership tasks | same three arms | 0/4, 0/4, 1/4 successful SQL attempts; 0 semantic wins | One diagnostic execution, but no accepted terminal answer or quality improvement |
| Governed held-out broker transfer | Llama 3.2, two harnesses, family-disjoint tasks | same three arms | all authority-valid; zero terminal submissions and zero semantic estimates | Model/protocol failure; not evidence for or against semantic skill benefit |
| Native governed SQL probe | Qwen 3 4B via Ollama-native API | same three arms | zero SQL tool calls and deterministic abstention in all arms | Typed model/runtime null; no quality claim |
| Trace2Skill stage-0 smoke | Pinned spreadsheet task | no-skill vs human-written skill | both passed after formula-verifier repair | One task with both arms passing; cannot estimate benefit |

The machine-readable source receipts are the corresponding files in
`experiments/results/`, especially:

* `model-harness-transfer-native-tool-2026-07-31.json`;
* `model-harness-transfer-llama-openai-vs-ollama-2026-07-31.json`;
* `natural-trace-skill-protocol-intervention-qwen3-4b-2026-07-31.json`;
* `defog-car-fallback-llama-2026-07-31.json`;
* `defog-family-transfer-broker-llama-2026-07-31.json`;
* `defog-qwen-native-probe-2026-07-31.json`; and
* `trace2skill-governed-stage0-2026-07-30.json`.

## Runtime boundary

The repository contains manifests for
`mlx-community/Qwen3.5-9B-OptiQ-4bit` at revision
`319aed167e31e0bf81ddba0c23f8d218a15be612`, but the pinned 7.1 GB snapshot is
not present on this machine and no Qwen3.5 listener is running. The available
live models are `llama3.2:latest` and `qwen3:4b`. Therefore, the Qwen3.5
manifest is an unexecuted plan, not evidence.

## Promotion rule

The current evidence supports **proposal-only** skill artifacts. A skill may
be promoted only after a family-disjoint, held-out replay has:

1. the same model and task schedule across no-skill, placebo, mined, and
   expert/SkillOpt/SkillGen/RHO arms;
2. an independent semantic verifier and an independent security/authority
   verifier;
3. accepted, semantically-correct terminal outcomes as the primary endpoint;
4. no regression in unauthorized observations, latency, token/tool budget, or
   abstention quality; and
5. replication across at least two harnesses or a pre-registered explanation
   for a harness-specific effect.

Until those gates pass, trace mining is useful for generating hypotheses and
candidate procedures, not for asserting that a user or team has improved a
skill.

## Next decisive experiment

Acquire or start the pinned Qwen3.5 runtime, then run the same governed SQL
factorial on family-disjoint tasks with sealed content and independent
verification. If that runtime cannot be reproduced, use a separately
validated SQL-specialist model and label the model substitution explicitly;
do not silently upgrade the claim.
