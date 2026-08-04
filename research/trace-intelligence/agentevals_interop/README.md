# AgentEvals v0.9.7 (2026-07-10)

**Repo:** [`agentevals-dev/agentevals`](https://github.com/agentevals-dev/agentevals)
at
[`221febbe05927923242a5edc12e68a2b70fd5ae9`](https://github.com/agentevals-dev/agentevals/tree/221febbe05927923242a5edc12e68a2b70fd5ae9)
**Release:** [`v0.9.7`](https://github.com/agentevals-dev/agentevals/releases/tag/v0.9.7)
**Package:** `agentevals-cli==0.9.7`
**License:** Apache-2.0; pinned license SHA-256
`3b1ee5b1e14fda40515c18ec2f0796d632e65a20b2aca8f017c654bc26ca77bd`

This directory contains a real upstream interoperability study, not a local
reimplementation of AgentEvals' matching semantics. It translates bounded
natural Claude Code histories into OTLP/GenAI spans and Google ADK eval sets,
then executes the installed upstream runner and evaluators.

## Commands

| Task | Command | Notes |
|---|---|---|
| Clone exact source | `git clone --depth 1 --branch v0.9.7 https://github.com/agentevals-dev/agentevals.git "$AGENTEVALS_UPSTREAM_ROOT"` | Tag resolves to the pinned commit above |
| Install exact lock | `cd "$AGENTEVALS_UPSTREAM_ROOT" && uv sync --frozen --no-group e2e` | Uses upstream `uv.lock`; lock SHA is in the aggregate result |
| Run focused deterministic tests | `AGENTEVALS_UPSTREAM_PYTHON="$AGENTEVALS_UPSTREAM_ROOT/.venv/bin/python" AGENTEVALS_UPSTREAM_ROOT="$AGENTEVALS_UPSTREAM_ROOT" python -m unittest discover -s tests -p 'test_agentevals_upstream_interop.py'` | Exercises the real upstream package |
| Start the local judge | `mlx_lm.server --model "$LOCAL_MODEL_SNAPSHOT" --host 127.0.0.1 --port 18082 --temp 0 --max-tokens 256` | Loopback only; model provenance is separately pinned |
| Run the natural cohort | `python -m agentevals_interop.run --corpus-root "$WISP_CORPUS_ROOT" --upstream-python "$AGENTEVALS_UPSTREAM_PYTHON" --upstream-root "$AGENTEVALS_UPSTREAM_ROOT" --raw-dir "$AGENTEVALS_RAW_DIR" --judge-base-url http://127.0.0.1:18082/v1 --output "$RESULT" --summary "$SUMMARY"` | Raw traces stay outside Git |
| Run upstream CLI directly | `agentevals run trace.otlp.json -e eval-set.json -f otlp-json -m tool_trajectory_avg_score --trajectory-match-type EXACT -o json` | Output contains trace content; keep it in the raw run directory |

## Config

| Option | Default | Notes |
|---|---:|---|
| `max_cases` | `3` | Content-hash-ordered complete natural histories |
| deterministic timeout | `30s` | Applied per upstream assertion |
| semantic timeout | `90s` | Applied per upstream judge assertion |
| match types | `EXACT`, `IN_ORDER`, `ANY_ORDER` | Upstream `ToolTrajectoryCriterion` modes |
| semantic metric | `final_response_match_v2` | Upstream ADK LLM-as-judge evaluator |
| semantic threshold | `0.5` | Upstream pass/fail threshold used in this run |
| raw artifact policy | external only | OTLP, eval sets, per-case scores, and driver specs are not committed |

## Environment variables

| Variable | Purpose |
|---|---|
| `AGENTEVALS_UPSTREAM_ROOT` | Exact v0.9.7 checkout |
| `AGENTEVALS_UPSTREAM_PYTHON` | Interpreter from its frozen environment |
| `AGENTEVALS_JUDGE_BASE_URL` | Loopback OpenAI-compatible judge endpoint used by the semantic test |
| `WISP_CORPUS_ROOT` | External pinned natural-history cache |
| `AGENTEVALS_RAW_DIR` | External content-bearing run directory |

## Gotchas

- `tool_trajectory_avg_score` ignores tool-call correlation IDs: all call-ID
  remaps passed. It compares tool names and arguments.
- `EXACT` and `IN_ORDER` both rejected sequence reversal in this cohort;
  `ANY_ORDER` passed it. Whether reordering is acceptable is task-specific.
- Every tool matcher passed a response reversal because response content is
  outside that metric. The semantic evaluator supplies distinct coverage.
- `final_response_match_v2` rejected one of three unmodified baselines while
  accepting every wrapped equivalent response. The judge is not safe as a
  singleton release gate.
- AgentEvals scores stored traces. It does not rerun an agent, execute a tool,
  verify a side effect, or test a changed Frankengate build.
- AgentEvals' JSON output includes expected and actual tool arguments. Never
  commit raw CLI output from enterprise traces.

## Sources

- CLI and match modes:
  [`src/agentevals/cli.py`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/cli.py#L76-L145)
- Built-in criteria and judge injection:
  [`src/agentevals/builtin_metrics.py`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/builtin_metrics.py#L176-L427)
- OTLP loader:
  [`src/agentevals/loader/otlp.py`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/loader/otlp.py)
- GenAI converter:
  [`src/agentevals/genai_converter.py`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/genai_converter.py)
- Eval-set contract:
  [`docs/eval-set-format.md`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/docs/eval-set-format.md)
- License:
  [`LICENSE`](https://github.com/agentevals-dev/agentevals/blob/221febbe05927923242a5edc12e68a2b70fd5ae9/LICENSE)
