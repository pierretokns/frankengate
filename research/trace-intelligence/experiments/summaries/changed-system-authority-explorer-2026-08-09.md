# Changed-system authority explorer probe

## Question

Can a frontier explorer select reusable artifacts safely when surface names
are stale, renamed, duplicated across systems, or attached to an old schema or
authority epoch? Does exposing typed metadata improve useful recall without
turning the model into the admission gate?

## Protocol

The fixture contains ten synthetic cases: unchanged artifacts, approved
renames, wrong-system collisions, schema drift, revoked artifacts, same-surface
ambiguity, temporal replacement, a no-safe-candidate NIL case, multiple valid
artifacts, and mixed drift. The evaluator hides which candidates satisfy the
contract. A candidate is valid only when all of these match:

```text
required semantic inputs + system ID + authority epoch + schema version + active status
```

Luna receives the same request twice per case:

1. `name_only`: candidate index and surface name only;
2. `typed_metadata`: immutable artifact ID, semantic inputs, system, epoch,
   schema, status, and evidence count.

The model may return an empty shortlist. It never sees the hidden valid-index
set, replay outcomes, or tool endpoints. There were 20 calls, zero failures,
and raw outputs remain external to the repository.

## Result

| Arm | Target found | Unsafe acceptance | Correct NIL abstention | Mean selected |
|---|---:|---:|---:|---:|
| Name only | `0.0` | `0.0` | `0.1` | `0.0` |
| Typed metadata | `0.9` | `0.0` | `0.1` | `1.0` |

Typed metadata found a valid candidate in all nine cases with at least one
valid candidate and abstained on the one NIL case. It did not select an invalid
candidate in any case. Name-only input caused complete abstention, including
all nine cases where a valid artifact existed; it was safe in this fixture but
not useful.

## Interpretation

This is a clean metadata-sufficiency result, not a claim that a frontier model
can enforce governance. The model can use typed metadata to make a good
candidate shortlist, but the deterministic typed admission contract must still
run after retrieval. Surface-name retrieval alone cannot distinguish a stale
artifact, wrong system, schema drift, same-name semantic collision, or revoked
artifact. The result supports the following architecture:

```text
typed metadata retrieval
  -> deterministic scope/semantic/epoch/schema/status gate
  -> independent replay or execution validation
  -> versioned artifact with expiry and rollback
```

The fixture is synthetic and does not measure enterprise alias quality,
production artifact utility, causal skill improvement, or cross-user transfer.
The next required experiment is the same arm comparison on an authorized,
task-disjoint trace cohort with reviewed wrong-system/NIL labels and actual
changed-system replay outcomes.

Receipts:

- [content-free result](../results/changed-system-authority-explorer-2026-08-09.json)
- [independent verification](../results/changed-system-authority-explorer-verification-2026-08-09.json)
- [`changed_system_authority_explorer_probe.py`](../../changed_system_authority_explorer_probe.py)
