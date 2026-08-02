# Deterministic artifact-capsule round-trip (2026-08-02)

This baseline compiles the same 10 coding episodes into content-external
artifact capsules without asking a model to infer identity or replayability.

## Capsule fields

Each action receives:

- stable `tool_id` derived from the tool name;
- unique `invocation_id` derived from order, tool name, and input keys;
- exact tool name and action order;
- exact input-key names;
- an externalized input-binding hash; and
- source-trace provenance hash.

The capsule explicitly marks execution, independent result validation, and
authority checks as false until those gates run.

## Results

On 10 bounded episodes:

| Round-trip property | Result |
| --- | ---: |
| Tool order | `1.000` |
| Input keys | `1.000` |
| Action order | `1.000` |
| Invocation IDs unique | `1.000` |
| Source provenance exact | `1.000` |

## Interpretation

The fields needed for artifact identity and parameter binding are losslessly
available in the raw trace and should be compiled deterministically. This
baseline avoids the model failure observed in the parameter-aware probe, where
repeated tool identity collapsed and `resource` was overloaded with concrete
paths. The model can still propose semantic aliases, phase labels, or
parameterized templates, but those proposals must attach to this deterministic
capsule rather than replace it.

This is a round-trip/mechanics result only. No command was replayed, no
authority was checked, and no artifact was promoted. The next artifact test
must execute these capsules against the original and a changed environment,
then compare independent results, side effects, stale authority, and user/task
utility.

## Receipts

- [machine-readable result](../results/cctrace-deterministic-capsule-roundtrip-2026-08-02.json)
- [independent verification](../results/cctrace-deterministic-capsule-roundtrip-verification-2026-08-02.json)
- [compiler](../../cctrace_deterministic_capsule_roundtrip.py)
- [verifier](../../verify_cctrace_deterministic_capsule_roundtrip.py)
- [parameter-aware model probe](cctrace-artifact-capsule-probe-2026-08-02.md)
