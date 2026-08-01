# SkillGen BIRD-SQL frontier reproduction (2026-08-02)

Status: **passed**. Pinned SkillGen ran on 8 BIRD-SQL train tasks using Codex and an independent SQLite execution oracle. Baseline: 2/8 passed; generated skill: True.

Held-out replay: `{'n': 8, 'baseline_acc': 0.5, 'skill_acc': 0.375, 'repair': 0, 'regression': 1, 'net_gain': -1, 'passed': False, 'baseline_failures': 4, 'baseline_successes': 4}`

The provider and hashed embedding substitutions are explicit. This is not native OpenRouter parity; promotion still requires repeated family-held-out cohorts and independent replay.
