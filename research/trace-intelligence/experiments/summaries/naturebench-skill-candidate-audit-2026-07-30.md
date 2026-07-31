# Natural-trace candidate extraction and transfer diagnostic

This audit mined a conservative procedure candidate from a successful
NatureBench Claude Code/Opus 4.7 trace and checked its predicates against four
same-task target outcomes. It supports candidate construction, not a causal
skill claim.

Candidate steps:

1. inspect the problem statement and data schema;
2. inspect task data;
3. check runtime, budget, and available tools;
4. write or edit a reproducible artifact;
5. evaluate or verify the output;
6. iterate after inspection.

| Arm | Historical status | Transcript | Candidate predicates complete |
| --- | --- | --- | --- |
| Claude Code / Opus 4.7 (source) | success | observed | yes |
| Claude Code / DeepSeek V4 Pro | timeout | observed | yes |
| Claude Code / GLM 5.1 | timeout | observed | yes |
| Codex / GPT-5.5 | success | observed | no (problem/schema read predicate differs) |
| Gemini CLI / Gemini 3.5 Flash | success | unavailable | typed null |

Three of four observed transcripts satisfied every predicate, including both
timeout runs. Codex succeeded while missing the Claude-specific read predicate.
That is exactly the expected confounding: protocol adherence is neither a
reliable success predictor nor evidence that the candidate caused an outcome.
The Gemini result has no transcript, so it cannot be scored.

The receipt is content-free: it stores source/result hashes, statuses, tool
event counts, and boolean predicates; raw transcripts stay in disposable
storage. The causal intervention remains open: inject this candidate into a
family-disjoint replay and compare no-skill, formatting placebo, expert,
trace-mined, SkillOpt, SkillGen, and RHO arms with independent verification,
paired repairs/regressions, cost/latency, and rollback gates.

Result: `experiments/results/naturebench-skill-candidate-audit-2026-07-30.json`.
