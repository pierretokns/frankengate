# Frontier transfer with a length-matched neutral control (2026-08-02)

## Design

This is a fresh four-task broker-family replay in a disposable PostgreSQL 16
container with a governed `NOSUPERUSER NOBYPASSRLS` role, a separate Codex
loopback proxy, and external raw/verifier audit roots. The four arms were
executed with the same model, tool budget, task order, schema injection, and
seed:

1. `no_skill`
2. `formatting_placebo`
3. `length_matched_neutral`
4. `trace_mined_terminal_discipline`

The neutral addition is exactly 308 characters, matching the trace artifact's
308-character addition, and contains no schema, SQL, identifier, or business
terms. The receipt records rendered character and word lengths for every arm.
All 16 trajectories passed independent semantic recomputation; authority and
security checks passed with zero unauthorized observations.

## Result

| arm | semantic correct | rate | submitted |
| --- | ---: | ---: | ---: |
| no skill | 1 / 4 | 0.25 | 4 / 4 |
| formatting placebo | 3 / 4 | 0.75 | 4 / 4 |
| length-matched neutral | 4 / 4 | 1.00 | 4 / 4 |
| trace-mined terminal discipline | 1 / 4 | 0.25 | 3 / 4 |

The trace-mined artifact lost to the neutral control on all three discordant
task blocks (risk difference −0.75; exact McNemar p=.25) and tied no-skill on
the paired endpoint (0.0; p=1.0). The neutral control beat no-skill 3–0
(p=.25). This is not powered evidence of a universal neutral benefit, but it
is strong protocol evidence against promoting this particular trace artifact:
its text did not outperform a same-length, domain-free control and reduced
terminal submission once.

## Interpretation and next gate

The result supports the existing cascade boundary: exact/structured and dense
retrieval can propose candidates; a frontier model can synthesize a candidate;
neither candidate is releasable without transfer evaluation. The next causal
gate must add renamed/paraphrased task mutants, train-only artifact selection,
at least one second harness, and multiple seeds. Promotion requires the
content arm to beat both no-skill and the length-matched neutral on those
transfer tasks with no submission, authority, latency, or cost regression.
