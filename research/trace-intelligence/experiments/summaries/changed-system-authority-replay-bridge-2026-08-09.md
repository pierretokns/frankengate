# Changed-system authority replay bridge

## Question

Does a frontier-selected artifact remain correct when it is actually executed,
and what fails if a system reuses a name without a typed admission gate?

## Protocol

The bridge consumes the 20 frontier receipts from the
[authority explorer probe](changed-system-authority-explorer-2026-08-09.md).
It replays every selected candidate against an independent in-memory SQLite
fixture covering ten changed-system cases. Each fixture includes approved
renames, wrong systems, stale epochs, schema drift, revoked artifacts,
same-surface semantic collisions, temporal replacement, a NIL case, multiple
valid artifacts, and mixed drift.

Three arms are reported:

1. `typed_metadata`: the frontier selection followed by the deterministic
   semantic/system/epoch/schema/status gate and independent SQL execution;
2. `name_only`: the name-only frontier selection, which may abstain;
3. `naive_name_first`: a deliberately unsafe control that selects the first
   name-bearing candidate and executes without the typed gate.

The model never supplies the replay result. The bridge executes SQL itself and
stores only hashes and aggregate outcomes in the receipt.

## Result

| Arm | Accepted executions | Safe/correct executions | Unsafe accepts | Result matches |
|---|---:|---:|---:|---:|
| Typed metadata + gate | `10` | `10` | `0` | `10` |
| Names only | `0` | `0` | `0` | `0` |
| Naive name-first control | `10` | `3` | `7` | `7` |

The typed arm executed the nine non-NIL valid cases (ten executions because
the multiple-valid case returned two valid artifacts) and every execution was
semantically correct. The name-only arm abstained. The naive name-first arm
accepted all ten cases, but seven were unsafe; seven happened to produce the
expected row digest, demonstrating why output equality alone cannot stand in
for authority or semantic validation.

## Interpretation

This is the first direct bridge from explorer selection to independent replay
in this program. It supports a strict separation:

```text
explorer shortlist
  -> typed admission gate
  -> replay/execution validator
  -> versioned artifact release
```

The result does not establish mined-artifact quality, enterprise prevalence,
production database behavior, or user utility. It is a synthetic SQLite
fixture and should be followed by the authorized P0 cohort with reviewed
semantic labels, real authority receipts, changed environments, and terminal
outcomes.

Receipts:

- [content-free result](../results/changed-system-authority-replay-bridge-2026-08-09.json)
- [independent verification](../results/changed-system-authority-replay-bridge-verification-2026-08-09.json)
- [`changed_system_authority_replay_bridge.py`](../../changed_system_authority_replay_bridge.py)
