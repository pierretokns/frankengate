# Public proxy cohort selection for trace-artifact learning (2026-08-06)

The repository now contains many public trace and text-to-SQL manifests. This
selection audit keeps dataset fit separate from causal enterprise claims. No
raw trace content is copied into the research branch.

## Best available proxies

| Dataset | What it can test | What it cannot establish | License / boundary |
|---|---|---|---|
| `experiential-labs/wmh-bird-sql-traces` | Recorded SQL-agent tool calls, observations, gold-linked outcomes, replay, and family-disjoint procedure mining. The pinned audit contains 1,993 joined traces, 1,978 bounded gold executions, and 11 database families. | No principal/team identity; no full assistant conversation, true OTel parentage, or real latency; SQLite replay is not PostgreSQL/Aurora evidence. | CC-BY-SA-4.0; external BIRD mini-dev environment required. |
| `birdsql/bird-interact-full` | Clarification and friction interventions: ambiguity labels, follow-up labels, user simulator, executable tests, and active/passive interaction modes. The public ADK also exposes 20 sample episodes with phase outcomes/rewards. | Simulator behavior is not natural employee history; the 20 samples are curated and tiny; full gold SQL/tests are withheld. | CC-BY-SA-4.0; evaluator/DB material must remain separated. |
| `defog-ai/sql-eval:enterprise-postgresql-96` | Governed SQL execution, schema-family holdouts, RLS/security checks, artifact retrieval, and controlled skill factorials. | No recorded agent trajectories or user identity; cannot answer natural friction, cross-user similarity, or enterprise prevalence. | Apache-2.0; gold/evaluator details remain sealed. |
| `trace-commons/agent-traces-full-claude-memory-composition` | Native multi-session Claude histories, memory-file interactions, tool/retry structure, and longitudinal candidate mining. | No stable principal labels or independent task outcomes; similarity is not evidence of collaboration or skill benefit. | CC-BY-4.0; content-minimized aggregate only. |
| `Edmon02/dataclaw-peteromallet` | Longitudinal single-user history mining: 549 sessions, 14 projects, and tool-use/re-prompt candidates. | It is one principal, lacks tool outputs, and is not a multi-user enterprise cohort. | MIT mirror; embedded third-party rights remain unresolved. |
| `microsoft/MAGIC` | Large-scale correction/self-correction and procedure-candidate mining (48,124 prompt/response/caller rows). | No raw tools, environment, database snapshot, or replayable outcome; cannot prove artifact execution or user benefit. | MIT project license plus dataset-card text-to-SQL research restriction. |
| `NJU-LINK/CodeTraceBench` | Repeated agent trajectories with solved/error/unuseful-step labels: 3,316 trajectories, including 1,000 verified and 405 with annotated error stages. | No SQL/schema/artifacts, user identity, authorization, or causal skill intervention. | MIT; trace-structure and failure-localization proxy only. |
| `hjerpe/analyst-buddy-traces` | Small paired base/fine-tuned SQL-agent recovery comparison with preserved observations. | Six tasks, one family, not independently replayable; no cross-schema or causal statistical claim. | CC-BY-SA-4.0. |

## Recommended empirical composition

No single public corpus answers the enterprise questions. The most defensible
proxy stack is:

1. **WMH-BIRD** for recorded trajectory → artifact/procedure → replayed SQL
   outcome;
2. **BIRD-Interact** for clarification, ambiguity, and repair-cost behavior;
3. **Trace Commons/DataClaw** for natural longitudinal friction and memory
   candidate discovery; and
4. **Defog** for governed PostgreSQL, security, schema drift, and artifact
   compatibility; and
5. **CodeTraceBench** for a separate structural failure/localization control,
   never as an SQL or enterprise-identity proxy.

The first two supply outcomes but not identity. The latter two supply history
structure but not causal outcomes. Joining them statistically would be invalid;
they should be separate intervention arms with the same canonical trace and
artifact schema.

## Next fair test

Use WMH-BIRD's 11-family split to run a preregistered no-skill, placebo,
reviewed-procedure, generated-procedure, and composable-subplan matrix. Mine
only evidence families, seal gold outcomes, report exact and unordered SQL
matches, repair regressions, tool calls, cost, latency, and abstentions. Use
BIRD-Interact only in a separate clarification arm. Do not infer identity,
cross-user transfer, or enterprise skill gaps from either public corpus.

Evidence inputs:

- [`wmh-bird-sql-traces.json`](../../configs/datasets/wmh-bird-sql-traces.json)
- [`bird-interact-enterprise-sql.json`](../../configs/datasets/bird-interact-enterprise-sql.json)
- [`defog-sql-eval-enterprise.json`](../../configs/datasets/defog-sql-eval-enterprise.json)
- [`recent-replay-dataset-fit-audit-2026-08-05.md`](recent-replay-dataset-fit-audit-2026-08-05.md)
- [`bird-sql-skill-factorial-powered-2026-07-31.md`](bird-sql-skill-factorial-powered-2026-07-31.md)
- [`changed-agent-outcome-bird-2026-08-02.md`](changed-agent-outcome-bird-2026-08-02.md)
