# External skill-learning refresh and Frankengate adaptation

This refresh covers recent methods that materially affect the next empirical
study. Their reported benchmark results are not treated as enterprise evidence
for Frankengate.

## Methods and exactness

| Method | Exact match to our problem? | What we should adopt | Hard edge in corporate traces |
|---|---|---|---|
| [SkillGen](https://arxiv.org/abs/2605.10999) | Closest to our desired skill intervention loop | Contrast successful and failed trajectories, synthesize an auditable skill, and evaluate the same instances with and without the skill. Count repairs and regressions separately. | Its verifier/task labels are not governed SQL/tool authority labels. Our replay must independently check semantic result, authority, schema epoch, and unsafe side effects. |
| [Trace2Skill](https://arxiv.org/abs/2603.25158) | Closest to broad trace-pool consolidation | Analyze diverse traces in parallel, propose patches, then conflict-check and consolidate a single skill before consumption. | A corporate trace pool mixes systems, tenants, versions, and permissions. Consolidation must be scope- and time-aware; a universal skill can encode the wrong system or stale authority. |
| [Trace2Skill for EDA](https://arxiv.org/abs/2605.21810) | Adjacent verifier-guided evolution | Feed bounded error/failure classes into a proposer, then use an oracle/mutator/selector loop behind replay. | Verifier observations can leak hidden SQL, rows, credentials, or policy decisions. Expose typed summaries only, and keep the acceptance oracle outside the proposer. |
| [SkillOpt](https://github.com/microsoft/SkillOpt) | Adjacent text-space optimizer | Reproduce epochs, candidate edits, validation gates, and a deployable skill artifact; report regressions, not just best-case wins. | Our two-task ALFWorld replication was a negative result, not a disproof. It used the wrong domain and too little headroom to establish whether SkillOpt transfers to governed tools. |
| [SkillLearnBench](https://github.com/cxcscmu/SkillLearnBench) | Benchmark framework, not an enterprise trace source | Reuse its separation of task success, skill quality, and trajectory quality; extend with authority, changed-system replay, and artifact identity. | Its public tasks have verifiers but not our multi-tenant scope, stale systems, or real tool side effects. |
| [AgentRx](https://github.com/microsoft/AgentRx) | Failure-diagnosis component | Convert raw traces to a trajectory IR, evaluate deterministic invariants, and retain evidence-backed first-fault reports. | A first fault is not necessarily semantic blame; retries, authority refusals, and alternative valid plans need separate classes. |
| [Agent Trajectories](https://github.com/AgentWorkforce/trajectories) | Artifact/provenance representation, not a learner | Preserve chapters, decisions, tool events, retrospectives, and links to commits/artifacts as reviewable provenance. | A retrospective is an observation/proposal, not a correctness label; never let it authorize replay or mutate memory automatically. |

## Why our negative results do not contradict the literature

Our current SkillOpt/Trace2Skill-style checks used public SQL/ALFWorld proxies,
small task counts, and weak or absent natural repetition. The strongest public
SQL artifact pool contained almost no repeated compatible procedures. Those
conditions can make a real method appear null even when its required inputs are
missing. Conversely, a positive skill-text score without changed-system replay
would not answer our enterprise question.

The fair reproduction therefore needs the method’s intended intervention:

```text
success + failure traces
  -> parallel diagnosis and lesson proposals
  -> conflict/identity/scope consolidation
  -> candidate skill artifact
  -> same-instance no-skill vs skill replay
  -> changed-system and authority replay
  -> repair/regression/unsafe/NIL accounting
```

## Required Frankengate extensions

1. **Run-level skill-in-use record:** skill ID/version, activation reason,
   bound scope/system/epoch, inputs, verifier observations, and rollback link.
2. **Typed bounded verifier output:** outcome class, error class, authority
   class, schema class, result-shape hash, repair count, and next-action gate;
   never raw rows, credentials, or hidden gold SQL.
3. **Contrastive candidate mining:** successes, failures, near-successes,
   wrong-system candidates, temporal replacements, and irrelevant exposed
   candidates must be separate strata.
4. **Same-instance paired evaluation:** measure repairs and regressions against
   the identical task set, then repeat on project-held-out and changed-system
   tasks.
5. **Consumption and outcome split:** skill quality and trajectory quality are
   intermediate metrics; promotion requires independent terminal outcome,
   safety, latency/cost, and user correction/acceptance evidence.

## Partner-facing contribution

The novelty is not another generic skill generator. It is adapting these
methods to **governed, multi-system enterprise traces** where a successful
output may still be unauthorized, stale, semantically wrong, or unsafe. The
publishable comparison is:

```text
no skill | neutral placebo | reviewed skill | SkillGen/Trace2Skill-style skill
         × exact/scope | dense | frontier review
         × source system | project-held-out | changed authority/schema
```

Report semantic correctness, authority validity, NIL abstention, repair rate,
regressions, unsafe accepts, cost/latency, and downstream task success
separately. This directly connects the current Frankengate receipts to the
methodological claims in the recent literature without importing their domain
assumptions.

## Claim boundary

These sources justify a stronger experimental design, not automatic promotion
of skills, memories, aliases, or embeddings. The required semantic labels and
prospective changed-system outcomes remain open.
