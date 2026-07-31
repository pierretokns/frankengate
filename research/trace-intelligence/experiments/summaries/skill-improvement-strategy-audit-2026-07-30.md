# Skill-improvement strategy audit

**Status:** external results reviewed; local mock plumbing passed; natural
Frankengate skill benefit remains untested.

## What changed

The earlier audit covered SkillOpt conceptually but did not inspect the current
Microsoft checkout or its newer Sleep/replay material. The current source is
pinned at `7da46ae693ee0329b80225c0128a37d65db10e9e`; the v0.2.0 release is
`51d0a4d96e88558c84dee637f98e24e3fb2d1547`.

The current implementation adds a nightly offline path: harvest → mine → replay
→ consolidate, with a held-out validation gate and staged adoption by default.
Its mock deterministic experiment ran locally:

```text
12 tasks; held-out baseline 0.3333; after 1.0; harmful edit blocked: true
```

That proves the gate and staging plumbing, not that a natural enterprise skill
improves work.

## External empirical evidence

SkillOpt reports 52/52 best-or-tied cells across seven target models, six
benchmarks, and multiple harnesses, with reported GPT-5.5 gains of +23.5 points
in direct chat, +24.8 in Codex, and +19.1 in Claude Code. The public aggregate
does not provide raw per-run artifacts or repeated-seed confidence intervals for
every cell.

The newer SkillOpt-Sleep analysis aggregates 499 run summaries. Its SearchQA
replay study reports +4.5 points with `recall_k=20` and +5.6 with full-history
replay. A paired ungated stress run fell from 55.4% to 2.6%, while the gated run
rejected the proposal and stayed at 57.0%. This is strong evidence for a gate,
not evidence that automatic adoption is safe.

RHO reports 59% → 78% on SWE-Bench Pro after one self-preference round, but it
has not been reproduced here and uses self-validation. SkillGen is more aligned
with Frankengate because it compares paired same-instance outcomes with and
without a candidate skill, explicitly counting repairs and regressions.

SigLeak is a security warning: execution traces can reveal proprietary skills.
Trace retention and cross-user similarity therefore require egress controls,
consent, and scoped projections even when the goal is improvement.

## Decision for Frankengate

Adopt the optimization *shape*: bounded candidate edits, frozen family-disjoint
splits, independent evaluation, strict regression gates, staged review, signed
release, rollback, and influence exclusion. Treat SkillOpt, RHO, SkillGen, and
Sleep as interchangeable proposal workers, never as authorities.

Do not claim that clustering or embeddings find useful cross-user work yet. The
best current E2 silver-label retrieval is Recall@20 = 0.818 (structured + exact
dense), versus 0.808 for structured + exact. These are publisher task identities
and metadata-derived negatives, not human-adjudicated “same work” labels. No
cross-user benefit, consent, or transfer outcome has been measured.

The decisive experiment is one common, family-disjoint corpus with no-skill,
placebo, expert, mined, SkillGen/SkillOpt/RHO candidate, and optimized arms;
paired repair/regression scoring; independently verified outcomes; and no
candidate access to hidden results. Until that exists, clustering is a review
queue and candidate-discovery aid, not a skill-sharing mechanism.

Machine-readable receipt: [`skill-improvement-strategy-audit-2026-07-30.json`](../results/skill-improvement-strategy-audit-2026-07-30.json).
