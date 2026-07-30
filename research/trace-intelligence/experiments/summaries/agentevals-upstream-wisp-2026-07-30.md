# Upstream AgentEvals natural-trace interoperability

**Study date:** 2026-07-30
**Execution:** AgentEvals v0.9.7 at `221febbe05927923242a5edc12e68a2b70fd5ae9`
**Natural cohort:** 3 complete multi-tool Wisp histories
**Claim boundary:** stored-trace assertions only; no changed system was executed

## Deterministic tool-trajectory assertions

| Mutation | EXACT | IN_ORDER | ANY_ORDER |
|---|---:|---:|---:|
| `baseline` | 1.000 (3/3 passed) | 1.000 (3/3 passed) | 1.000 (3/3 passed) |
| `benign_id_remap` | 1.000 (3/3 passed) | 1.000 (3/3 passed) | 1.000 (3/3 passed) |
| `benign_response_wrapper` | 1.000 (3/3 passed) | 1.000 (3/3 passed) | 1.000 (3/3 passed) |
| `sequence_reversal` | 0.000 (0/3 passed) | 0.000 (0/3 passed) | 1.000 (3/3 passed) |
| `harmful_tool_drop` | 0.000 (0/3 passed) | 0.000 (0/3 passed) | 0.000 (0/3 passed) |
| `harmful_argument_corruption` | 0.000 (0/3 passed) | 0.000 (0/3 passed) | 0.000 (0/3 passed) |
| `harmful_response_reversal` | 1.000 (3/3 passed) | 1.000 (3/3 passed) | 1.000 (3/3 passed) |

## Upstream semantic response assertion

AgentEvals `final_response_match_v2` was executed with its pinned ADK judge path and a pinned, loopback-only Qwen3.5-9B model. This is a model-judge result, not deterministic ground truth.

| Mutation | Mean score | Passed | Failed | Errors |
|---|---:|---:|---:|---:|
| `baseline` | 0.667 | 2 | 1 | 0 |
| `benign_response_wrapper` | 1.000 | 3 | 0 | 0 |
| `harmful_response_reversal` | 0.000 | 0 | 3 | 0 |

The semantic judge caught all 3/3 response reversals and accepted all 3/3
benign wrappers, but it also rejected 1/3 unmodified baselines. That
non-monotonic false negative is direct evidence against using this judge alone
as a release gate.

## What this mechanism contributes

- `EXACT` detects any tool-name/argument/order divergence.
- `IN_ORDER` tests an expected ordered subsequence, so it can tolerate additional calls but not a reversal or a missing expected call.
- `ANY_ORDER` isolates membership/argument equality from ordering; the reversal arm demonstrates its incremental contribution.
- `final_response_match_v2` tests response-level semantic equivalence separately from tool-path equivalence.

## Limits

- These evaluations score already-recorded traces. They do not rerun an agent, tool, environment, side effect, or changed Frankengate build.
- A passing stored-trajectory assertion is therefore retrospective compatibility evidence, not a changed-system regression result.
- Call-ID remapping is intentionally benign and demonstrates that the tool evaluator compares names and arguments, not trace correlation IDs.
- Sequence reversal is a structural sensitivity probe; it is not labeled benign or harmful without task-specific commutativity evidence.
- The semantic arm uses one local judge model and one deterministic template-level benign/harmful mutation pair. Human labels and multiple judge families are required before estimating semantic accuracy.
- Raw prompts, responses, tool arguments, and per-case scores remain in the external run directory. This repository contains aggregates only.

## Reproduction

```bash
PYTHONPATH=research/trace-intelligence \
python -m agentevals_interop.run \
  --corpus-root "$WISP_CORPUS_ROOT" \
  --upstream-python "$AGENTEVALS_UPSTREAM_PYTHON" \
  --upstream-root "$AGENTEVALS_UPSTREAM_ROOT" \
  --raw-dir "$AGENTEVALS_RAW_DIR" \
  --judge-base-url http://127.0.0.1:18082/v1 \
  --output experiments/results/agentevals-upstream-wisp-2026-07-30.json \
  --summary experiments/summaries/agentevals-upstream-wisp-2026-07-30.md
```
