# Public BIRD trace model-vs-trajectory cascade (2026-08-08)

## Question

Does a frontier model gain useful artifact judgment from the recorded SQL tool
call beyond the natural-language question, and can it emit a replayability/
validator contract? This is a public-data probe; no private local traces were
sent to the frontier harness.

## Protocol

- 16 balanced BIRD trace cases: eight whose recorded SQL independently matched
  the gold result and eight whose recorded SQL executed but did not match.
- **Prompt-only arm:** question only.
- **Trajectory arm:** question plus the recorded SQL tool call.
- Model: `gpt-5.6-luna` through the Codex subscription harness.
- Gold correctness stayed in the evaluator and was not shown to the model.
- Required JSON: artifact match (true/false/null), replayability, validator
  type, and confidence.

## Result

| Arm | Valid JSON | Predicted true | True positives | False positives | Abstentions |
|---|---:|---:|---:|---:|---:|
| Prompt only | 16/16 | 0 | 0 | 0 | 16 |
| Recorded trajectory | 16/16 | 13 | 7 | 6 | 2 |

The trajectory arm achieved **87.5% recall** on correct artifacts and **53.8%
precision** among its positive predictions. It over-accepted six incorrect
artifacts. The prompt-only arm was perfectly conservative but produced no
usable artifact judgment. The trajectory arm labeled nine cases replayable,
but replayability was not independently validated by the model; only the
hidden SQLite result comparison establishes correctness.

## Interpretation

1. Tool context adds real signal that prompt-only text does not provide.
2. A frontier model can produce a valid structured contract reliably on this
   small public sample.
3. The model is not a release gate: six false positives are unacceptable for
   automatic artifact reuse. Independent replay, authority, scope, and schema
   checks remain mandatory.
4. The right cascade is therefore **structured/exact retrieval → trajectory
   model for candidate ranking and validator suggestion → independent replay**,
   not model-only semantic acceptance.

This is not evidence of enterprise intent understanding or user benefit; BIRD
gold correctness is a task proxy, not human adjudication.

## Receipts and code

- [aggregate receipt](../results/bird-trace-model-cascade-16-2026-08-08.json)
- [independent verification](../results/bird-trace-model-cascade-16-2026-08-08-verification.json)
- [`bird_trace_model_cascade.py`](../../bird_trace_model_cascade.py)
- [`verify_bird_trace_model_cascade.py`](../../verify_bird_trace_model_cascade.py)
- [`test_bird_trace_model_cascade.py`](../../tests/test_bird_trace_model_cascade.py)

