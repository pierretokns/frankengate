# Trace2Skill-style compiled procedure: contamination correction and disjoint replay

## What was tested

The first replay (seed 430000) was initially described as held-out transfer.
An audit of the raw JSONL showed that the compiler source files and the replay
contained the same four broker task IDs. That result is therefore a
**contaminated development smoke**, not evidence of transfer. It remains useful
only for verifying compiler plumbing and isolation.

The authoritative disjoint replay (seed 440000) compiled from six car-
dealership trajectories (two task IDs) and evaluated on four different broker
task IDs. Each arm received a fresh Postgres container, role, port, raw-audit
root, and independent semantic verifier:

1. no skill
2. formatting placebo
3. length-matched neutral control
4. a Trace2Skill-style compiled procedure produced from disjoint governed JSONL
   source files by three independent frontier analyst roles (protocol, SQL,
   transfer) plus a separate frontier consolidator

The disjoint compiler artifact is
`experiments/results/trace2skill-defog-compiled-car-to-broker-candidate-2026-08-02.json`.
It is explicitly `promotion_authorized: false` and emits no raw trace content
or authority identifiers.

## Result

| Arm | Semantic correct | Rate | SQL attempts | Unauthorized observations |
|---|---:|---:|---:|---:|
| no skill | 3/4 | 0.75 | 6 | 0 |
| formatting placebo | 4/4 | 1.00 | 6 | 0 |
| length-matched neutral | 3/4 | 0.75 | 4 | 0 |
| disjoint Trace2Skill compiled procedure | 3/4 | 0.75 | 8 | 0 |

The disjoint compiled arm tied no-skill and neutral on all four paired episodes;
exact two-sided McNemar p=1.0. The formatting placebo won one episode against
each of those arms. Independent semantic recomputation passed for all four
arms; authority was valid for every episode and unauthorized observations were
zero.

## Interpretation

The corrected result does **not** show transfer utility. It does show that a
multi-agent trajectory-to-procedure compiler can produce an auditable candidate
and that the candidate can be replayed under governed isolation. The only
cross-database outcome is null on this four-task, one-seed slice. The original
430000 positive must not be used as evidence because of source/replay overlap.

The useful boundary is therefore:

* **Supported:** parallel analyst/consolidator compilation is implementable; the
  artifact can be hashed, audited, and replayed under governed isolation.
* **Not supported:** cross-database transfer, universal transfer, causal skill
  benefit, human utility, cross-user generalization, or production promotion.
* **Next test:** use multiple disjoint source/evaluation families, user/project
  and time splits, and a negative-transfer cohort; require a preregistered
  minimum lift over both no-skill and neutral controls plus artifact review and
  changed-database replay.

## Receipts

* Contaminated development candidate: `experiments/results/trace2skill-defog-compiled-candidate-2026-08-02.json`
* Disjoint compiled candidate: `experiments/results/trace2skill-defog-compiled-car-to-broker-candidate-2026-08-02.json`
* Merged isolated receipt: `experiments/results/defog-codex-frontier-native-trace2skill-car-to-broker-seed-440000-merged-2026-08-02.json`
* Independent verification: `experiments/results/defog-codex-frontier-native-trace2skill-car-to-broker-seed-440000-merged-independent-verification-2026-08-02.json`
* Aggregate: `experiments/results/trace2skill-car-to-broker-native-seed-440000-aggregate-2026-08-02.json`
* Overlap gate (contaminated 430000): `experiments/results/trace2skill-overlap-audit-contaminated-2026-08-02.json`
* Overlap gate (contaminated sequential prefix): `experiments/results/trace2skill-overlap-audit-sequential-prefix-2026-08-02.json`
* Overlap gate (authoritative disjoint replay): `experiments/results/trace2skill-overlap-audit-car-to-broker-2026-08-02.json`

All raw trajectories remain outside the repository.
