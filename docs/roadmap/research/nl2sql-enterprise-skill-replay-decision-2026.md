# Enterprise NL2SQL as Frankengate's primary skill-replay domain

**Status:** architecture decision plus executable fixture and sandbox smoke  
**Date:** 2026-07-30  
**Decision:** prioritize governed NL2SQL replay; retain spreadsheets as a small
cross-domain execution control

## Outcome

NL2SQL is the strongest available empirical domain for the enterprise questions
Frankengate is meant to answer. It combines deterministic external outcomes,
multi-step tool use, private business knowledge, memory, schema retrieval,
clarification, repair, cost, and authorization. Spreadsheet manipulation does
not exercise enough of that surface to justify the primary research budget.

The smallest architecture remains:

1. Frankengate OTel/OpenInference traces with messages, model calls, tool calls,
   SQL, database results, policies, costs, and outcomes as typed events.
2. One governed PostgreSQL/Aurora authority for traces, evidence, candidates,
   evaluations, releases, exposure, influence, and rollback.
3. One isolated replay worker that can query only disposable public/synthetic
   databases through a read-only, bounded SQL tool.
4. Harness projections such as `SKILL.md` or `MEMORY.md` only after an immutable
   release decision.

No second database, graph service, standalone vector store, or generic agent
platform is required for the first study.

## Why this domain answers the enterprise questions

[Spider 2.0](https://github.com/xlang-ai/Spider2) raises average schema width
from about 27 columns in Spider 1.0 to about 804 and gold SQL length from 18.5
to 144.5 tokens; its agentic setting also requires project and tool navigation.
[EntSQL](https://arxiv.org/abs/2606.03363) reports that 96% of 1,066 examples
need enterprise-private knowledge. In its English evaluation, concise evidence
improved Claude Code from 6.8% to 21.4%, while full documents reached only
15.9%. This is exactly the distinction Frankengate needs to test: schema alone,
structured evidence selection, long-context stuffing, and durable memory are
not equivalent.

[NL2SQLBench](https://github.com/neurodb/NL2SQLBench) decomposes performance
into schema selection, candidate generation, and revision. Gold schema raises
execution accuracy by roughly 15–20%, semantic errors dominate syntax errors,
and revision sometimes changes correct SQL into incorrect SQL. These are
observable skill dimensions, unlike a generic judgment that a user is "bad at
SQL."

[FINCH](https://arxiv.org/abs/2510.01887) adds finance-specific schemas and
materiality-aware scoring. Its reported best execution accuracy is 7.5%, and
its curation found large numbers of broken inherited queries. The broader
warning is confirmed by the CIDR audit and its
[corrected corpus](https://github.com/uiuc-kang-lab/text_to_sql_benchmarks):
more than half of audited BIRD and Spider 2.0-Snow examples contained an
annotation issue. Public benchmark gold cannot be trusted without audit,
execution, and distinguishing rows.

## What the earlier trace and memory concepts contribute

| Concept | Use in NL2SQL | Do not import |
| --- | --- | --- |
| [Signals](https://arxiv.org/abs/2604.00356) | Cheap detection of failed commands, repeated schema probes, loops, stagnation, rephrasing, and disengagement on every trace | A failure label or skill judgment based on a signal alone |
| [AgentRx](https://github.com/microsoft/AgentRx) | Canonical trajectory, deterministic invariants, failure taxonomy, and decisive-step proposals | An unverified root-cause assertion |
| [AgentEvals](https://github.com/agentevals-dev/agentevals) | Turn a production trajectory into ordered, unordered, exact, or semantic regression assertions | Retrospective trace matching as a substitute for database replay |
| [Trace2Skill](https://github.com/Qwen-Applications/Trace2Skill) | Contrast pooled success and failure traces and preserve localized patch proposals | Direct mutation of a live skill |
| [SkillOpt](https://github.com/microsoft/SkillOpt) | Select bounded candidates on a frozen selection split | Force-accept, ungated slow updates, or access to hidden test outcomes |
| [ReasoningBank](https://github.com/google-research/reasoning-bank) | Induce retrievable procedural lessons from successes and failures | Self-judged reward or benchmark-contaminated retrieval |
| [Graphiti](https://github.com/getzep/graphiti) | Provenance, time-valid business rules, contradictions, and entity relationships | A second graph database or `group_id` as authorization |
| [LangMem](https://github.com/langchain-ai/langmem) | Structured candidate extraction and consolidation operations | Direct store mutation without evidence and release lineage |
| Phoenix, Opik, and Langfuse | Trace, dataset, annotation, experiment, and feedback lifecycle concepts | Three additional production observability authorities |

These mechanisms compose at typed evidence boundaries:

```text
trace and database outcome
  -> cheap signals
  -> localized failure proposal
  -> candidate procedure or memory
  -> selection replay
  -> hidden schema-family test
  -> signed scoped release
  -> influenced production traces
  -> prospective outcome evaluation
```

They do not compose safely as multiple agents writing the same file or as
multiple stores deciding who may see a derived artifact.

## First factorial

Use the frozen 96-task Defog cohort (95 currently PostgreSQL-executable) and
split before candidate generation by database/schema family. The first 46-task
`statebench/finance-retrieval-sql-v0` fixture is only a control seed: all 46
internal checks pass, but only four tasks currently execute gold SQL.
[Defog SQL-Eval](https://github.com/defog-ai/sql-eval) is the preferred
execution scaffold because it already supports local schemas and executable
result comparison. It is not the source of truth for task quality.

The frozen task strata must cover:

- schema/table/column selection;
- missing or ambiguous join keys;
- aggregations, windows, dates, fiscal periods, and as-of logic;
- concise private business rules versus full documents;
- clarification and multi-turn carry-forward;
- PostgreSQL dialect and at least one portability control;
- unauthorized rows, columns, literals, and cross-tenant semantic neighbors;
- revision traps where a correct first answer can be degraded.

Run the same model, tool schema, seed, token budget, and database snapshot in
the following preregistered arms. Each learned artifact must be evaluated alone
before composition:

1. no learned procedure;
2. an unrelated but plausible SQL-skill placebo;
3. raw retrieved trajectories;
4. single-failure reflection;
5. schema-navigation/table-column skill;
6. time-valid business-rule and metric skill;
7. dialect/function skill;
8. verified question-to-SQL exemplars;
9. failure-to-repair procedure;
10. pooled synthesis plus held-out selection;
11. Signals + AgentRx localization + pooled synthesis + held-out selection;
12. the preregistered strongest composition.

Cross only the strongest arms with:

- current turn only;
- bounded working memory;
- episodic trace retrieval;
- structured, time-valid business-rule memory.

Also compare schema only, structured table/column selection, concise business
evidence, and full-document context. Do not add dense retrieval until exact
identifiers, PostgreSQL full-text search, and typed metadata fail on a frozen
business-rule hard slice.

## Metrics and release rule

Primary quality is executed result correctness on hidden schema families, not
SQL string equality. Also report:

- table and column precision/recall;
- incorrect-to-correct and correct-to-incorrect revision rates;
- pass@k and abstention/clarification correctness;
- repeated/failed tool calls, loops, latency, tokens, and database runtime;
- evidence precision for selected business rules;
- per-family regression floors;
- zero unauthorized rows, columns, tool results, or memory evidence.

Use paired bootstrap intervals and McNemar tests. A candidate can ship only if
it improves the frozen selection score, passes every policy check, causes no
material family regression, and then improves the untouched test split. Any
authorization leak is a hard zero regardless of answer accuracy.

## Database and execution controls

The model-facing database role must be `NOSUPERUSER NOBYPASSRLS`, must not own
tables, and must run a read-only transaction with:

- `SELECT`-only parse validation;
- statement, lock, idle, row, and result-byte limits;
- an `EXPLAIN` cost gate;
- a disposable schema or database reset per task;
- policy and authorization-epoch context set before query planning;
- same-query and semantic-neighbor cross-tenant negative controls.

Trace the SQL proposal and database result independently. Tool calls must remain
first-class events; flattening them into conversational text prevents reliable
failure localization and policy audit.

## Hard edges

1. Execution agreement can be a false positive when the fixture lacks
   distinguishing rows.
2. A correct result can still be unauthorized; correctness and authority are
   separate axes.
3. Public gold SQL can be wrong; task audit and corrected fixtures are required.
4. A trace can show a failure but cannot by itself prove the user's missing
   skill or the cause.
5. A procedure useful on one schema can overfit identifiers and harm another.
6. Private business rules change over time; memory requires valid time,
   transaction time, provenance, contradiction, and withdrawal.
7. Cross-user recommendations require explicit scope, minimum support,
   de-identification, and prospective benefit measurement.
8. Fine-tuning a SQL or embedding model is premature until a frozen failure
   slice shows that retrieval/prompt/procedure changes cannot close the gap.

## Current empirical state

- The real model/tool sandbox executed a paired SpreadsheetBench smoke test.
  Both no-skill and human-skill arms pass after correct formula recalculation;
  the test establishes execution mechanics, not skill benefit.
- The StateBench finance fixture passes all 46 internal consistency checks in
  its SQLite smoke runner. This is not PostgreSQL, RLS, or Aurora proof.
- The governed PostgreSQL lifecycle now passes 18/18 rollback-only assertions
  through distinct proposer, evaluator, releaser, and runtime roles. It proves
  candidate provenance, hidden-test isolation, security-vetoed release, scope
  non-broadening, exposure/influence lineage, withdrawal, and stale-epoch
  denial. It does not prove SQL skill quality or Aurora behavior.
- The Defog source audit froze 96 tasks across four database families. The
  hardened PostgreSQL runner matches all 95 executable tasks. Under the default
  policy, 93 match, two sensitive projections are correctly denied, and both
  match only under explicit field entitlements. One upstream task is invalid
  PostgreSQL and is quarantined. All parser, missing-epoch, and database
  read-only controls pass on all four families. Sensitive-field inference
  through predicates, joins, grouping, ordering, windows, functions, and
  correlated subqueries is now denied without entitlement; the entire cohort
  requalified with the same 93/2/1 distribution. This remains a verifier/policy
  self-check, not a model-quality result.
- The cache-disabled four-task F0 mechanics smoke completed all 12
  no-skill/placebo/expert-seed episodes. Every arm solved the same 2/4 tasks,
  all authority receipts were valid, and no unauthorized observation occurred.
  Terminal-protocol failure was 25%, 50%, and 25%, respectively. The
  preregistered protocol and paired-win gates failed, so the 23-task selection
  screen and hidden broker family remain sealed.
- The Spider2 audit found 135 local Lite tasks across 30 families, but only
  16/24 published gold SQL files pass upstream self-check. Of 68 DBT tasks, 59
  are strictly self-consistent and 62 work after deterministic filename
  aliases; the proposed later external-validity cohort is 60. The upstream
  agent's ordinary tool actions execute twice, so its runner is not reusable
  without repair.
- The next gate is an arm-independent terminal-protocol remediation on a
  separate protocol fixture, followed by a new complete P0 under new hashes.
  Only after it passes may the 23-task selection screen run. BIRD remains the
  mined-procedure source and Spider2 the later external-validity layer.

CMU is not on the critical path. Its access is gated and the admitted public
trace and SQL sources are sufficient.
