# Trace2Skill compiled procedure: car-to-broker transfer replication

Date: 2026-08-02

## Protocol

This is a complete frontier-native transfer run, distinct from the earlier
18-file compiled pilot. The compiler saw six hash-addressed source histories
from the Defog `car_dealership` family (two task IDs, each with no-skill,
formatting-placebo, and trace-mined source arms). It produced a new procedure
before replay. The replay cohort used four different `broker` task IDs.

Each arm used a fresh governed PostgreSQL container, role, port, raw-audit
root, and independent semantic verifier. Raw trajectories and SQL remain
outside the repository; committed receipts contain hashes and aggregate
outcomes only.

## Results

| Arm | Semantic correct | Rate | SQL attempts | Tool calls | Unauthorized observations |
| --- | ---: | ---: | ---: | ---: | ---: |
| no skill | 3/4 | 0.75 | 6 | 14 | 0 |
| formatting placebo | 4/4 | 1.00 | 6 | 14 | 0 |
| length-matched neutral | 3/4 | 0.75 | 4 | 12 | 0 |
| compiled procedure | 3/4 | 0.75 | 8 | 16 | 0 |

The compiled arm tied no-skill on all four paired episodes, tied the neutral
control on all four, and lost to the formatting placebo on one episode. Exact
two-sided McNemar p=1.0 for every pair. All four arm receipts passed independent
semantic recomputation with zero stored/recomputed mismatches; authority was
valid for all 16 episodes.

## Interpretation

This is a clean **family-transfer null for incremental utility**. It shows that
a procedure compiled from car-domain trajectories can be executed safely on a
different broker task family, but it does not improve semantic success and
increases SQL/tool attempts relative to no-skill. The result therefore
strengthens the distinction between:

* candidate grounding and replayability, which are working;
* transferability, which is possible but inconsistent; and
* task-level improvement, which is not yet demonstrated.

The formatting placebo reaching 4/4 is an additional warning that uncontrolled
prompt length/style effects can dominate a small candidate-versus-baseline
comparison. The compiler artifact remains `promotion_authorized: false`.

This is not a disproof of Trace2Skill, SkillLearnBench, SkillFlow, SkillOpt, or
any related paper. It is a null under one model, one seed, four target tasks,
and one source/target family split. It does reject promoting this artifact or
claiming generic enterprise skill lift.

## Receipts

* Candidate: `experiments/results/trace2skill-defog-compiled-car-to-broker-candidate-2026-08-02.json`
* Merged arms: `experiments/results/defog-codex-frontier-native-trace2skill-car-to-broker-seed-440000-merged-2026-08-02.json`
* Aggregate: `experiments/results/trace2skill-car-to-broker-native-seed-440000-aggregate-2026-08-02.json`
* Independent verification: `experiments/results/defog-codex-frontier-native-trace2skill-car-to-broker-seed-440000-merged-independent-verification-2026-08-02.json`

The next valid gate remains a powered sequential cohort with multiple source
and target families, changed schemas, negative-transfer tasks, no-skill/placebo/
neutral controls, cost/latency/abstention limits, and independent human or
sealed semantic labels.
