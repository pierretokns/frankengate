# Integrity correction: composable artifact frontier replay

The first run wrote to the default receipt path
`experiments/results/composable-artifact-frontier-replay-2026-08-04.json`.
A concurrent worker later overwrote that path. Its current SHA-256 is
`92f62ed54f788a8f71df2c75b69f7f91c3e300b35a7c56770cb580cf17cc9e0e`, while the
paired verifier does not reference that digest. The default result is therefore
quarantined and must not be used as evidence.

The authoritative replay uses unique receipt paths, each independently checked
by a semantic verifier:

- seed 840000 rerun result: `1f4fde983c63357731201e28d3bc3e31f664c0ad4c9d68a963b9f160d4cef54e`;
- seed 850000 result: `3f944c8e49f0c163158c1cc68b1f53af5d5e4b3214e26f4afadd9877528bf17d`;
- aggregate result: `965e1d45791803e7ba62b380cb6ea2ba6261d93943586e7650f5c6fea8f2812b`.

Those two valid seeds aggregate to composable `10/10`, no-skill `5/10`, and
formatting-placebo `5/10` semantic correctness over ten repeated episodes of
five unique source-disjoint broker tasks. The unique-task comparison is three
stable wins, zero stable losses, and two ties-or-mixed tasks against either
control. The seeds are replications, not ten independent tasks. No authority
violations or semantic-verifier errors occurred.

This correction preserves the overwritten artifact for auditability while
preventing it from silently changing the published result.
