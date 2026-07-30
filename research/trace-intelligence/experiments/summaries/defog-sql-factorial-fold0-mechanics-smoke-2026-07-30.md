# Defog F0 governed SQL mechanics smoke

## Result

The frozen four-task F0 mechanics smoke completed 12/12 paired episodes under
the final cache-disabled MLX runtime and governed PostgreSQL policy. It
successfully qualified the native tool and authority path, but it failed the
preregistered protocol gate and provides no evidence that the expert seed
improves SQL quality.

| Arm | Joint/semantic pass | Strict answer shape | Terminal submissions | Missing terminal | Protocol-failure rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| No skill | 2 / 4 | 2 / 4 | 3 / 4 | 1 / 4 | 25% |
| Formatting placebo | 2 / 4 | 2 / 4 | 2 / 4 | 2 / 4 | 50% |
| Expert schema-navigation seed | 2 / 4 | 2 / 4 | 3 / 4 | 1 / 4 | 25% |

Every arm passed the same two tasks. There were no paired pass discordances:
expert-minus-placebo and expert-minus-baseline risk differences are both zero
on this deliberately inadequate sample. McNemar inference is uninformative
with zero discordant pairs and four tasks.

The content-free aggregate is
`experiments/results/defog-sql-factorial-fold0-mechanics-smoke-2026-07-30.json`
with SHA-256
`508c78b367a791e125f83c5dfdc1f82d2363ef558d9d299812c448fe683ec250`.
Raw questions, prompts, model messages, schema, SQL, database observations, and
answers remain in the external audit directory and are not committed.

## What worked

- All 12 episodes validated the exact current database/scope/user/team/virtual
  key authorization epoch.
- All 12 used native tool calls, inspected the authorized schema, and attempted
  SQL.
- All 12 remained free of unauthorized observations.
- The server used the immutable local 9B snapshot through request alias
  `default_model`; no mutable repository resolution occurred.
- Server logs showed prompt cache `0 sequences, 0.00 GB` before every request.
- Submitted SQL selected an already executed opaque attempt ID. The evaluator
  did not execute the candidate again.
- Benchmark execution accuracy and strict output-label accuracy agreed on every
  task.
- Every aggregate receipt contains model, runtime, prompt, tool, design,
  dataset, authority, runner, attempt-chain, and raw-audit hashes.

## Cheap trace signals

The raw external tool events show why the protocol gate failed without needing
an LLM judge:

| Signal | No skill | Placebo | Expert |
| --- | ---: | ---: | ---: |
| Successful SQL tool results | 6 | 4 | 6 |
| Policy denials | 2 | 2 | 0 |
| Database errors | 0 | 2 | 1 |
| Calls after exhausting the three-attempt SQL budget | 2 | 4 | 2 |
| Accepted terminal submissions | 3 | 2 | 3 |

One task produced three successful SQL attempts in both baseline and expert
arms but still ended without `submit_sql`. The same task ended without a
terminal action in every arm. This is a direct stagnation/tool-protocol signal:
the small model sometimes keeps calling `execute_sql` after it already has
usable evidence instead of selecting an attempt.

Across all arms the run used 51 model calls, 51 tool calls, 23 admitted SQL
attempts, 16 successful SQL executions, 74,385 prompt tokens, 9,306 completion
tokens, and 241.124 seconds of measured model-request latency. These are
mechanics costs for a local non-frontier model, not serving benchmarks.

## Gate disposition

The visible 23-task effect screen and hidden broker family remain sealed.

| Preregistered condition | Result |
| --- | --- |
| Complete task/arm receipts | Pass |
| Zero unauthorized observations | Pass |
| No arm above 10% protocol failures | **Fail**: 25%, 50%, and 25% |
| Expert has at least two more paired wins than losses versus placebo | **Fail**: 0 wins, 0 losses |

Running 69 additional episodes under the unchanged harness would be wasteful:
the endpoint would be dominated by terminal-protocol failure, and the four-task
smoke shows no intervention sensitivity. The next action is a frozen,
arm-independent protocol remediation—tested outside selection/hidden
families—followed by a complete P0 rerun under new hashes. It must not be tuned
using hidden outcomes.

Candidate remediations to compare on a separate protocol fixture are:

1. make `submit_sql` the only available tool after a successful third attempt;
2. include the explicit remaining schema/SQL/turn budget in every tool result;
3. test a stronger pinned native-tool model; and
4. retain the current behavior as a negative control.

Any adopted change creates a new experiment version and invalidates this P0 for
effect estimation. It does not alter the published null/mechanics result.

## Claim boundary

This run proves that the frozen local path can exercise native tool calls,
governed PostgreSQL, exact current-epoch authorization, terminal attempt
receipts, and offline evaluation. It does not estimate causal skill benefit,
trace-mined skill benefit, schema transfer, hidden-test performance,
enterprise-user improvement, Aurora behavior, or production RLS safety.
