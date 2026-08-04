# SkillGen Codex frontier reproduction (2026-08-02)

Status: **passed**. The run used the pinned upstream checkout through a Codex `exec` adapter, with a deterministic hashed embedding substitute. This is an independent bounded reproduction, not an OpenRouter-equivalent or benchmark efficacy result.

- Codex calls: 16
- Generated skill: False
- Baseline trajectories: 8 (8 successes, 0 failures)
- Elapsed seconds: 153.062

The provider and embedding substitutions are explicit because SkillGen hard-codes OpenRouter/OpenAI clients. Any generated artifact is exploratory and is not eligible for promotion without held-out, repeated evaluation.
