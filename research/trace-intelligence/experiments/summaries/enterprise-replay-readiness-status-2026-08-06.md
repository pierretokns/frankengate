# Enterprise changed-system replay readiness status (2026-08-06)

## Result

The readiness gate is executable, but no current public cohort is eligible for
causal changed-system replay.

| Input | Result | Meaning |
|---|---:|---|
| Public Defog-derived NL2SQL cohort | `42` records; `ready_for_causal_replay=false` | It has questions, candidates, and gold-SQL focus proxies, but lacks principals, projects, systems, time, two blinded labels, changed environments, hard-negative labels, and independent outcomes. |
| Synthetic protocol fixture | `100` records; `ready_for_causal_replay=true` | The schema and admission checks work. This is a harness self-test, not evidence about agents or enterprise users. |

The public cohort must therefore remain a retrieval/mechanics proxy. A shape
pass cannot be converted into a utility claim by adding fabricated metadata.

## Required authorized-data handoff

The first real cohort should be exported through a content-minimized adapter
with the following fields per task: consent-scoped principal/team/project/system
IDs, effective time, source and changed-environment hashes, complete tool/result
trajectory, two blinded semantic labels plus `nil`/`unclear`, an independent
terminal outcome, and deletion/retention receipts. Raw prompts, SQL, arguments,
rows, and identifiers remain outside the repository.

The minimum gate is 100 labeled targets, 50 hard negatives, 25 NIL/unclear
labels, at least two principals/projects/systems, two changed environments,
unique task IDs, and complete required values. Passing this gate only permits
the preregistered replay; it does not guarantee a skill or artifact win.

## Receipts and code

- Public cohort rejection: [`enterprise-replay-cohort-readiness-nl2sql-2026-08-05.json`](../results/enterprise-replay-cohort-readiness-nl2sql-2026-08-05.json)
- Synthetic gate self-test: [`enterprise-replay-protocol-selftest-2026-08-05.json`](../results/enterprise-replay-protocol-selftest-2026-08-05.json)
- Checker: [`enterprise_replay_cohort_readiness.py`](../../enterprise_replay_cohort_readiness.py)
- Protocol self-test: [`enterprise_replay_protocol_selftest.py`](../../enterprise_replay_protocol_selftest.py)

