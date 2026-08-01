# Trace2Skill-style compiled procedure: isolated native replay

## What was tested

This is a bounded, preregistered-style follow-up to the earlier Defog family-transfer pilots. Four frontier Codex CLI arms ran against the same four pinned broker tasks and the same governed Postgres benchmark, but each arm received a fresh Postgres container, role, port, raw-audit root, and independent semantic verifier:

1. no skill
2. formatting placebo
3. length-matched neutral control
4. a Trace2Skill-style compiled procedure produced from 18 governed JSONL source files by three independent frontier analyst roles (protocol, SQL, transfer) plus a separate frontier consolidator

The compiler artifact is `experiments/results/trace2skill-defog-compiled-candidate-2026-08-02.json`. It is explicitly `promotion_authorized: false` and emits no raw trace content or authority identifiers.

## Result

| Arm | Semantic correct | Rate | SQL attempts | Unauthorized observations |
|---|---:|---:|---:|---:|
| no skill | 3/4 | 0.75 | 6 | 0 |
| formatting placebo | 3/4 | 0.75 | 8 | 0 |
| length-matched neutral | 3/4 | 0.75 | 6 | 0 |
| Trace2Skill compiled procedure | 4/4 | 1.00 | 7 | 0 |

The compiled arm beat each control on one paired episode and tied on three. Exact two-sided McNemar p=1.0 for each comparison. Independent semantic recomputation passed for all four arms; authority was valid for every episode. This is a positive directional pilot, not evidence of general skill utility.

## Interpretation

This result is the first direct evidence in this repository that a multi-agent trajectory-to-procedure compiler can produce a candidate that transfers to a held-out prompt set without leaking the raw traces. It does **not** show that Trace2Skill itself is validated for enterprise SQL, nor that the candidate should be promoted. The sample is only four tasks and one seed, and the candidate contains conservative SQL-process guidance that may be especially well matched to this benchmark.

The useful boundary is therefore:

* **Supported:** parallel analyst/consolidator compilation is implementable; the artifact can be hashed, audited, and replayed under governed isolation; this pilot is directionally positive.
* **Not supported:** universal transfer, causal skill benefit, human utility, cross-user generalization, or production promotion.
* **Next test:** repeat across independent task families, users/projects/time splits, and a negative-transfer cohort; require a preregistered minimum lift over both no-skill and neutral controls plus artifact review and changed-database replay.

## Receipts

* Compiled candidate: `experiments/results/trace2skill-defog-compiled-candidate-2026-08-02.json`
* Merged isolated receipt: `experiments/results/defog-codex-frontier-native-trace2skill-seed-430000-merged-2026-08-02.json`
* Independent verification: `experiments/results/defog-codex-frontier-native-trace2skill-seed-430000-merged-independent-verification-2026-08-02.json`
* Aggregate: `experiments/results/trace2skill-native-seed-430000-aggregate-2026-08-02.json`

All raw trajectories remain outside the repository.
