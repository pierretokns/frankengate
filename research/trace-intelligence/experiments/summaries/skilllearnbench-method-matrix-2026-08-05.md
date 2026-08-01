# SkillLearnBench matched-method preflight (2026-08-05)

The frozen matrix uses the same 20 tasks and the same Claude Sonnet 4.6
solving model for six arms:

1. no skill (null baseline);
2. human-authored skill;
3. one-shot skill generation;
4. self-feedback;
5. teacher-feedback; and
6. skill-creator.

All five non-null arms contain artifacts for all 20 tasks, and every arm uses
the same task-set hash. The preflight therefore prevents task-set or artifact
coverage differences from being mistaken for learning value.

This is only an execution preflight. It does not run Docker agents, measure
verifier outcomes, or establish enterprise transfer. The required execution
dependencies are Docker, the Anthropic model runtime, and the published judge
runtime. Once run, the result must report pass rate, skill quality,
trajectory/key-point quality, cost, and negative transfer before any operator
is ported into Frankengate’s changed-system protocol.

Receipt:
[`skilllearnbench-method-matrix-2026-08-05.json`](../manifests/skilllearnbench-method-matrix-2026-08-05.json)
