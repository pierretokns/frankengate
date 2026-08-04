# Recent skill, replay, and enterprise-retrieval prior art (2026-08-05)

This update separates papers/tools that are exact matches for the Frankengate
objective from adjacent methods that contribute one mechanism. None of the
results below is evidence that a private corporate trace corpus will improve
users without labels and changed-system outcomes.

## Directly adaptable mechanisms

| Source | What it actually contributes | Frankengate adaptation | Boundary |
|---|---|---|---|
| [SkillAdaptor](https://arxiv.org/abs/2606.01311) | Step-level first-actionable-fault attribution, skill responsibility links, and targeted updates with acceptance checks while keeping the backbone frozen | Add a fault-step → candidate artifact/skill link, require evidence and replay checks, and update only the implicated procedure | Reported gains are on WebShop/PinchBench/Claw-Eval; no corporate aliases, governed SQL, or cross-user outcomes |
| [HASP](https://arxiv.org/abs/2605.17734) | Converts passive lessons into executable Program Functions that trigger on failure-prone states and alter the next action | Represent validated SQL/tool artifacts as typed executable functions with preconditions, scope, validator, expected evidence, and rollback | Strong web/math/coding claims do not establish enterprise safety or artifact relevance |
| [Recovery-Bench](https://github.com/letta-ai/recovery-bench) | Replays failed commands into a fresh corrupted environment, then measures recovery success on the same failure set | Make trace-mined eval promotion require replay of the failure state and a changed-system recovery outcome | Terminal-Bench environments are not governed enterprise systems; the replay contract is the reusable idea |
| [Hard Negative Mining for Domain-Specific Retrieval](https://arxiv.org/abs/2505.18366) | Dynamically selects semantically close but contextually irrelevant documents for enterprise reranker training | Mine same-scope/different-system, stale-version, granularity, and alias-collision negatives before any domain adapter | Proprietary cloud corpus and reported improvements are not independently reproduced here |

## Evaluation and library infrastructure

| Source | Useful contribution | Why it is not a drop-in answer |
|---|---|---|
| [SkillLearnBench](https://github.com/cxcscmu/SkillLearnBench) | 20 tasks/100 verified instances; separates task success, skill quality, and trajectory quality; includes one-shot, self-feedback, teacher-feedback, and Skill Creator baselines | Public task domains lack Frankengate authority, SQL schema drift, user identity, or enterprise outcomes |
| [SkillRL](https://github.com/aiming-lab/SkillRL) | Hierarchical skill bank, successful/failed trajectory distillation, recursive evolution, and token-compression analysis | Requires substantial RL/SFT infrastructure; use its representation and failure-memory ideas before attempting policy co-training |
| [Trace2Skill](https://github.com/Qwen-Applications/Trace2Skill) | Parallel trajectory-local patch proposals followed by conflict-free skill consolidation | Spreadsheet/math/VQA tasks do not solve corporate scope, alias, or authorization; the patch/consolidation protocol is reusable |
| [AgentReplay](https://github.com/agentreplay/agentreplay) | Local-first trace/memory/eval product with causal traversal and vector indexes | Product performance numbers are vendor claims; its embedded database is an architecture comparison, not evidence of retrieval or skill utility |

## What this changes in the experimental program

1. **Separate diagnosis from revision.** Use AgentRx/SkillAdaptor-style first
   fault attribution to select a candidate update; never revise a whole skill
   from a session-level “failure” marker.
2. **Make artifacts executable.** A promoted SQL/tool artifact should look more
   like a HASP Program Function than a paragraph: trigger, typed inputs,
   authority scope, validator, expected evidence, and rollback.
3. **Replay before release.** Adopt Recovery-Bench’s failure-state replay
   contract for eval promotion and changed-system gates.
4. **Treat hard negatives as first-class data.** The current Frankengate result
   already shows exact/identifier-aware lanes beating generic dense retrieval;
   the next adapter study should use mined same-scope and temporal negatives,
   not only random distractors.
5. **Keep the causal endpoint unchanged.** The decisive measure remains paired
   next-task outcome, negative transfer, cost/latency, and reviewer utility—not
   skill text quality or nearest-neighbor recall alone.

Tracking: [skill improvement #111](https://github.com/pierretokns/frankengate/issues/111),
[artifact reuse #119](https://github.com/pierretokns/frankengate/issues/119),
[hard negatives #123](https://github.com/pierretokns/frankengate/issues/123), and
[embedding adaptation #121](https://github.com/pierretokns/frankengate/issues/121).
