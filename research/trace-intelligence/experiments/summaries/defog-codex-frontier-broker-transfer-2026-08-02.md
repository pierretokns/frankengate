# Codex/Luna frontier family-transfer replay (2026-08-02)

## Protocol

This is the first frontier-model run in the governed Defog SQL harness. The
model path was `gpt-5.6-luna` through the authenticated Codex CLI subscription,
behind a loopback-only OpenAI-compatible research proxy. The proxy translated
the existing tool-loop messages into structured Codex responses; it did not
send public task data to a third-party API outside that subscription.

The run used four family-disjoint `broker` tasks. The candidate procedure was
mined from the separate `car_dealership` cohort. All three arms received the
same authorized schema catalog and execution limits:

- `no_skill`
- formatting placebo
- trace-mined terminal-discipline candidate

Raw prompts, SQL, rows, model responses, and temporary role credentials remain
outside Git. The aggregate receipt is
[`defog-codex-frontier-broker-transfer-2026-08-02.json`](../results/defog-codex-frontier-broker-transfer-2026-08-02.json).

## Results

| Arm | Semantic correct | Submitted | SQL attempts | Tool calls |
| --- | ---: | ---: | ---: | ---: |
| no-skill | 0/4 | 3/4 | 3 | 10 |
| formatting placebo | 3/4 | 4/4 | 6 | 14 |
| trace-mined candidate | 3/4 | 4/4 | 4 | 12 |

The [independent verifier receipt](../results/defog-codex-frontier-broker-transfer-independent-verification-2026-08-02.json)
re-executed every submitted candidate and sealed gold alternative in governed
PostgreSQL: 12/12 stored outcomes matched, zero verifier errors, and zero
unauthorized observations.

## Interpretation

The trace-mined candidate beats the no-skill arm in this four-task sample, but
it ties the formatting placebo exactly (3/4). Therefore the result does **not**
show artifact-specific skill value or authorize promotion. It does show that a
frontier model can reach the governed replay path and that independent
semantic/security verification is operational.

The next causal gate is a larger preregistered family-held-out sample with
multiple seeds, an independently adjudicated artifact, and a placebo matched
for prompt length and protocol instructions. This run remains exploratory:
the Codex proxy did not expose provider token usage or a deterministic model
seed, so it is not a final effect-size estimate.
