# Nebius matched-task deterministic-signal pilot

**Run date:** 2026-07-30
**Status:** completed preliminary mechanism test; not a product result
**Dataset revision:** `68195a1450865274106246d0d0296a1d6807b88e`
**Input SHA-256:** `6d1f9fcd171f036e37a486fd5eeff68fd06f2c4ccef96cc60d20049b2535219e`

## Design

The pilot used 300 public
[`nebius/SWE-agent-trajectories`](https://huggingface.co/datasets/nebius/SWE-agent-trajectories)
attempts from 30 task IDs. Every task contributed five externally successful and five
externally failed attempts. Task IDs were selected and attempts ordered with stable
hashes. The balanced design supports within-task mechanism comparison; it cannot
estimate natural failure prevalence.

The adapter preserved all 11,490 source turns. Because the source represents commands
and environment results as alternating chat messages rather than explicit spans, their
tool semantics are marked `reconstructed`. The adapter does not invent timestamps,
authorization decisions, tool-call IDs, latency, provider IDs, or branches.

Signals were computed without reading the outcome:

- syntax, missing-resource, permission, and test-error patterns;
- repeated and immediately repeated actions;
- repeated results and error classes; and
- rejected edit loops.

The fixed score was compared with trace length at a 20% review budget. External failure
is only a proxy for “worth reviewing”; it is not a gold diagnosis label.

## Results

| Arm | Failure-proxy precision at 20% budget | Enrichment over 50% base | Failure recall | AUROC |
|---|---:|---:|---:|---:|
| Deterministic friction score | 73.3% | +23.3 points | 29.3% | 0.639 |
| Trace length | 76.7% | +26.7 points | 30.7% | 0.609 |

Task-cluster bootstrap, 1,000 replicates:

| Estimate | Friction score 95% interval | Length 95% interval | Paired friction − length 95% interval |
|---|---:|---:|---:|
| Failure-proxy precision | 61.7%–86.7% | 66.7%–88.3% | −11.7 to +6.7 points |
| Enrichment | +11.7–+36.7 points | +16.7–+38.3 points | −11.7 to +6.7 points |
| AUROC | 0.583–0.692 | 0.554–0.668 | −0.006 to +0.064 |

Failed attempts were longer on average (48.2 versus 28.4 turns), had more repeated
actions (11.0 versus 2.9), and had more syntax-error observations (3.73 versus 0.61).
Those are associations inside this benchmark, not causes or skill evidence.

## Interpretation

The deterministic signals contain outcome information, but this pilot does not show
that their composite beats the trivial length baseline. The AUROC direction is
favorable, while the top-budget precision direction is unfavorable, and both paired
confidence intervals include zero.

This result blocks any claim that Signals-style screening is already ready for the
Frankengate review queue. The next valid test needs blinded human labels for
“diagnostically informative,” a mandatory random audit stratum, and a score frozen
before the holdout is opened. It should also test each signal independently: the
current fixed weights may dilute useful loop/stagnation evidence with generic failure
terms.

## What this pilot proves

- Native non-OTel trajectories can be admitted without silently relabeling inferred
  tool semantics as observed facts.
- Cheap, label-blind features can be executed over hundreds of full trajectories in
  seconds without embeddings or model calls.
- Matched failed/successful cohorts are available for later recovery-delta and
  decisive-step annotation.

## What it does not prove

- that failure is equivalent to a trace worth reviewing;
- that a signal identifies the decisive failure step;
- that an observed recovery delta caused success;
- that public coding traces transfer to Frankengate enterprise work;
- that any person lacks a skill; or
- that a memory, eval, prompt, or skill suggestion improves later work.

The executable harness and conformance tests live in
[`research/trace-intelligence`](../../README.md).
