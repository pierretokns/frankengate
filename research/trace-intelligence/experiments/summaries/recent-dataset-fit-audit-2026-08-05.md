# Recent trace/skill dataset fit audit (2026-08-05)

This audit distinguishes datasets that can supply a missing label/outcome from
repositories that only provide a storage or orchestration pattern.

| Dataset/repository | Directly supports | Does not support | Frankengate use |
|---|---|---|---|
| [Recovery-Bench](https://github.com/letta-ai/recovery-bench) | Failed trajectories, reproducible corrupted environments, recovery success after replay | Corporate identity, aliases, team skill gaps, governed SQL authority | First public replay benchmark for diagnose→replay mechanics; use its failure-set/recovery split |
| [TRAIL benchmark](https://github.com/patronus-ai/trail-benchmark) | 148 annotated traces and 841 reasoning/execution/planning errors | User intent, cross-user transfer, changed enterprise systems | AgentRx/Signals failure taxonomy and first-fault attribution calibration |
| [SkillLearnBench](https://github.com/cxcscmu/SkillLearnBench) | 20 skill-dependent tasks, 100 verified instances, task/skill/trajectory metrics, continual-learning baselines | Private schema, authority scope, temporal validity, enterprise user outcomes | Reproduce one-shot/self-feedback/teacher-feedback arms before adapting to SQL |
| [SkillRL](https://github.com/aiming-lab/SkillRL) | Successful/failed trajectory distillation and hierarchical skill-library representation | A controlled changed-system causal benchmark; substantial RL/SFT dependencies | Representation and compression ablation only; do not start with RL infrastructure |
| [Trace2Skill](https://github.com/Qwen-Applications/Trace2Skill) | Parallel trajectory-local patch proposals and conflict-free consolidation | Independent enterprise semantic labels and authorization | Patch/consolidation implementation arm in the existing replay protocol |
| [AgentReplay](https://github.com/agentreplay/agentreplay) | Local trace ingestion, causal traversal, vector/index architecture | Independently verified retrieval or skill utility; public labeled outcomes | Architecture comparison only; not a benchmark replacement |
| [Hard Negative Mining for Domain-Specific Retrieval](https://arxiv.org/abs/2505.18366) | A published enterprise hard-negative selection recipe and public-proxy evaluation claims | Reproducible proprietary cloud corpus or corporate alias labels | Reimplement negative families on Defog, then on an authorized sealed corpus |

## Acquisition order

1. Run Recovery-Bench and TRAIL as independent diagnosis/recovery calibration;
   they are the closest public sources for missing failure labels and replay
   outcomes.
2. Run the SkillLearnBench baseline matrix on one SQL/tool task family to
   verify our harness can separate task success, skill quality, and trajectory
   quality before adding enterprise data.
3. Admit an authorized enterprise cohort only after its schema satisfies the
   readiness receipt: stable principal/project/system/time, two labels,
   hard-negative/NIL strata, changed environments, and independent outcomes.
4. Port only the mechanisms that survive those gates into Frankengate; do not
   import a new database or RL stack merely because a repository advertises
   higher throughput or benchmark gains.

This fit audit leaves the main scientific question intact: whether a
diagnosed, validated, executable artifact improves a held-out changed-system
task without wrong-scope or negative-transfer failures.
