# Changed-system replay from natural Wisp assertions

**Study date:** 2026-07-30
**Cohort:** 3 pinned natural Wisp trajectories
**Actual runtime invocations:** 18 (each system-task pair executed twice to verify reset)
**Upstream evaluator:** AgentEvals v0.9.7 at `221febbe05927923242a5edc12e68a2b70fd5ae9`

## Result

This experiment executes three different **system implementations**. It does not mutate a stored output and call that a changed-system test. Each implementation runs against a fresh state machine whose required transitions, expected tool path, observed tool results, task prompt, and final response are derived from the same source-pinned natural trajectory.

| System implementation | Outcome-complete | EXACT | IN_ORDER | ANY_ORDER |
|---|---:|---:|---:|---:|
| `original` | 3/3 | 3/3 passed | 3/3 passed | 3/3 passed |
| `benign_audit` | 3/3 | 0/3 passed | 3/3 passed | 3/3 passed |
| `harmful_drop` | 0/3 | 0/3 passed | 0/3 passed | 0/3 passed |

The original system completed all source-derived transitions. The benign system did the same and appended an audit-only tool call. The harmful system omitted the final required transition and was incomplete according to the replay state—not according to the AgentEvals score.

## Prospective regression metrics

| Assertion | Original false positives | Benign false positives | Harmful recall | Errors |
|---|---:|---:|---:|---:|
| `EXACT` | 0.0% | 100.0% | 100.0% | 0 |
| `IN_ORDER` | 0.0% | 0.0% | 100.0% | 0 |
| `ANY_ORDER` | 0.0% | 0.0% | 100.0% | 0 |

`EXACT` caught the harmful omission but also rejected every benign audit addition. `IN_ORDER` and `ANY_ORDER` caught every harmful omission while accepting the benign extra call in this cohort. This is prospective regression evidence for this replay model, not an accuracy estimate for production.

## Evidence preserved

- 3 source files are frozen by content SHA-256 and verified against Hugging Face cache revision `c2c90b59174318ab0b163ec9c9ac82bb879288ce`.
- Every expected and emitted tool path, paired tool-result evidence set, prompt, and final response has a content digest in the input manifest or aggregate case receipts.
- Content-bearing source JSONL, OTLP, eval sets, and per-case AgentEvals records remain in the external run directory.
- Each system-task pair ran twice; equality of both executions and a zeroed pre-state are required before scoring.
- The AgentEvals module was loaded from the verified v0.9.7 checkout; the runtime reported AgentEvals 0.9.7 and Google ADK 2.1.0.

## Claim boundary and failure modes

- The executed target is a resettable **opaque transition replay**, not the original Hyprland desktop, shell, filesystem, network, model, or user session.
- Historical Bash arguments are preserved as evidence and assertion inputs but are never executed. This avoids unsafe, irreproducible side effects while sacrificing environment fidelity.
- Replay completion means all source-derived transitions were applied. It does not prove that the historical user task was correct or that its recorded final response was truthful.
- The harmful arm is one deterministic omission. Argument corruption, wrong-but-plausible tool results, timeouts, nondeterminism, reordered commutative actions, provider changes, and semantic-response failures remain untested changed-system families.
- The cohort contains three content-hash-selected trajectories from one public contributor and includes benchmark traffic. It cannot estimate enterprise prevalence or transfer.
- `IN_ORDER` and `ANY_ORDER` tolerate extra calls. That was desirable for an audit-only addition here, but could hide harmful unasserted side effects. Separate invariants and outcome oracles remain required.

## Reproduction

```bash
PYTHONPATH=research/trace-intelligence python3 \
  research/trace-intelligence/changed_system_replay_run.py \
  --cache-root "$WISP_CACHE_ROOT" \
  --dataset-manifest research/trace-intelligence/configs/datasets/wisp-claude-code-sessions.json \
  --experiment-config research/trace-intelligence/configs/experiments/changed-system-replay-v1-2026.json \
  --upstream-python "$AGENTEVALS_UPSTREAM_PYTHON" \
  --upstream-root "$AGENTEVALS_UPSTREAM_ROOT" \
  --raw-dir "$CHANGED_SYSTEM_RAW_DIR" \
  --input-manifest research/trace-intelligence/experiments/manifests/changed-system-replay-wisp-2026-07-30.json \
  --output research/trace-intelligence/experiments/results/changed-system-replay-wisp-2026-07-30.json \
  --summary research/trace-intelligence/experiments/summaries/changed-system-replay-wisp-2026-07-30.md
```

## Sources

- [Wisp dataset at the pinned revision](https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions/tree/c2c90b59174318ab0b163ec9c9ac82bb879288ce)
- [AgentEvals v0.9.7](https://github.com/agentevals-dev/agentevals/tree/221febbe05927923242a5edc12e68a2b70fd5ae9)
- [AgentEvals built-in metric construction](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/builtin_metrics.py#L176-L191)
- [Google ADK trajectory match semantics](https://github.com/google/adk-python/blob/6d15e19f057ee4035960ba5984499cb1eaf943ca/src/google/adk/evaluation/eval_metrics.py)
