# Structural friction signals in the Ronald DataClaw export

## Measurable signals

The 436-session OpenAI-format projection contains 5,785 user messages and
47,863 assistant messages with tool calls. It has:

- 19 adjacent exact-repeat user pairs;
- 121 adjacent lexical-rephrase pairs;
- 49 sessions containing a repeat or rephrase pair; and
- 1,131 user messages containing simple retry/error/friction markers.

These are useful review-prioritization signals, but they are not labels of
friction, satisfaction, intent, or missing skill. A rephrase can be productive
scope refinement, and a marker can be quoted documentation or a normal status
update.

## Format limitation

The projection has **zero explicit `tool` role messages** across all sessions;
tool calls are represented on assistant messages, but tool results are not
available as separately typed observations. Consequently, this corpus cannot
support a valid error-to-success or tool-failure recovery measurement. The
receipt records that boundary explicitly rather than treating assistant text as
tool output.

## Decision

Use adjacent rephrase/retry structure to prioritize a review queue and to sample
candidate evals. Require explicit tool-result events, independent terminal
outcomes, and human or second-model adjudication before labeling a friction
episode or promoting a skill/memory. A future importer should preserve
`tool_call -> tool_result -> user correction` edges as first-class trajectory
events.

Receipt: [`dataclaw-ronald-structural-friction-audit-2026-08-02.json`](../results/dataclaw-ronald-structural-friction-audit-2026-08-02.json)

Audit implementation: [`dataclaw_structural_friction_audit.rb`](../../dataclaw_structural_friction_audit.rb)
