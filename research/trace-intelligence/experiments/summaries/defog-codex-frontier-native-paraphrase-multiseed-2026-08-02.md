# Native Codex paraphrase transfer with per-arm database isolation (2026-08-02)

## Design

This is the balanced direct Codex CLI replication of the paraphrased broker
task screen. Seeds 400000 and 410000 used the earlier disposable-container-per-
seed runner. Seed 420000 used the stronger isolation mode: each arm received a
fresh Postgres container, governed role, loopback port, raw audit directory, and
independent verifier. The 420000 arm receipts were merged only after all four
arm-level verifications passed.

All seeds used the same four renamed/paraphrased tasks, schema injection, model
family, tool budget, and independent semantic/security/authority checks. The
aggregate is descriptive and is not a claim of universal skill utility.

## Results

| arm | semantic correct | rate | paired comparison |
| --- | ---: | ---: | --- |
| no skill | 8 / 12 | 0.667 | baseline |
| formatting placebo | 10 / 12 | 0.833 | +2 vs no-skill; exact McNemar p=.625 |
| length-matched neutral | 9 / 12 | 0.750 | +1 vs no-skill; p=1.0 |
| trace-mined terminal discipline | 9 / 12 | 0.750 | tied neutral; +1 vs no-skill; p=1.0 |

The trace artifact did not beat the length-matched neutral control (1 win each,
10 ties; risk difference 0.0) and did not beat the formatting placebo. It used
fewer SQL attempts/tool calls than the placebo, but this is not evidence of
better answers because semantic accuracy tied neutral. Every arm had 12/12 valid
authority receipts, zero unauthorized observations, and passed independent
semantic recomputation.

## Interpretation

This replication removes the earlier one-seed native ambiguity: on this task
family and direct harness, the trace artifact is at best equivalent to a
domain-free same-length addition. The proxy paraphrase aggregate was mildly
positive for trace (8/12 vs neutral 7/12), so the cross-harness discrepancy is
real enough to treat harness/serialization as a confound, not as evidence for
promotion. The result still does not disprove the underlying skill-mining
literature; it rejects promotion of this artifact under this protocol.

## Receipts

- Aggregate: `experiments/results/defog-codex-frontier-broker-transfer-docker-native-paraphrase-multiseed-aggregate-2026-08-02.json`
- Per-arm isolated seed: `experiments/results/defog-codex-frontier-broker-transfer-docker-native-seed-420000-merged-2026-08-02.json`
- Per-arm independent verification: `experiments/results/defog-codex-frontier-broker-transfer-docker-native-seed-420000-merged-independent-verification-2026-08-02.json`
- Stronger runner: `frontier_transfer_docker_arm_isolated.py`
