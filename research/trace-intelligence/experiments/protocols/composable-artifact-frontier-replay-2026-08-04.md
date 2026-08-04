# Composable artifact frontier replay — 2026-08-04

## Motivation

The whole-query artifact pool coverage ceiling found no reusable source query
for any of ten held-out targets. This replay tests a different hypothesis:
validated source queries may still provide useful schema-aware subplans or
patterns that a frontier agent can compose into a new query.

## Cohort and leakage

- Five broker `questions_gen_postgres.csv` targets from the pinned enterprise
  manifest are used as future tasks.
- The candidate library is built only from governed-success broker artifacts
  in `instruct_basic_postgres.csv` and `instruct_advanced_postgres.csv`.
- Target questions, target SQL, target result rows, and target IDs are not
  included in the candidate library.
- The library is presented as examples/subplans, not as an authority to copy a
  complete query. The agent must inspect the authorized schema and execute its
  own candidate.
- Raw candidate text, prompts, SQL, tool calls, and rows remain in an external
  audit directory; committed receipts contain hashes and aggregate outcomes.

## Arms

1. `no_skill`: fixed governed SQL agent without added artifact context.
2. `formatting_placebo`: same-length procedural attention control without
   schema, SQL, identifier, or business semantics.
3. `trace2skill_compiled_procedure`: validated source-query subplan library plus
   explicit composition/parameterization/abstention instructions.

All arms use the same direct Codex native JSON harness, model, task order,
authority epoch, tool schemas, schema access, model-turn/SQL-attempt limits, and
seed. The candidate arm is not allowed to submit a stored source query without
revalidating it against the current target schema and request.

## Endpoints

Primary: semantic correctness with valid authority and no unauthorized
observation. Secondary: SQL attempts, tool calls, terminal protocol failures,
latency, and negative transfer. The result is a small family-level replay, not
a powered enterprise causal estimate; promotion requires larger family/time/
project-held-out replication and changed-schema replay.
