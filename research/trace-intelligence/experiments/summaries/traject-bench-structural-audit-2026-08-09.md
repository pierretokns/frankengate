# TRAJECT-Bench structural audit (2026-08-09)

## Purpose

This is a deterministic schema/coverage audit of the public
[TRAJECT-Bench repository](https://github.com/PengfeiHePower/TRAJECT-Bench).
It did not invoke a model, call an external tool, or execute a benchmark
trajectory. Raw queries, tool descriptions, parameters, and outputs remain in
the disposable downloaded checkout; the committed receipt contains hashes and
aggregate counts only.

## Measured coverage

| Measure | Result |
|---|---:|
| Records | 5,910 |
| Parallel records | 4,000 |
| Sequential records | 1,910 |
| Tool invocations described | 38,094 |
| Invocations with non-empty recorded output | 37,313 (97.95%) |
| Parameter values present | 70,426 / 71,789 (98.10%) |
| Sequential records marked executable | 1,870 / 1,910 |
| Records containing duplicate tool names | 681 |
| Explicit connected-tool metadata fields | 0 |
| Tool-count consistency errors | 0 |
| Successful-tool-count consistency errors | 0 |

The data covers ten domains, with 2,000 parallel “hard/simple” records and
1,710 sequential records whose file naming does not encode that query variant.
The sequential dependency is represented by ordered tool lists and prose
sequence descriptions, not a structured dependency-edge field.

## What this establishes

1. It is a strong public fixture for testing trajectory metric adapters:
   selection, parameter completeness, ordering, duplicate/redundant calls,
   execution-status handling, and parallel versus sequential paths.
2. The zero consistency errors mean Frankengate can ingest the published
   records without silently changing the declared tool counts.
3. Duplicate tool names are common enough that a set-only metric would lose
   information; order and multiplicity must remain in the canonical trajectory.
4. The 40 non-executable sequential cases and the recorded error outputs are
   useful negative/abstention fixtures, but they are benchmark-generated
   failures, not natural enterprise friction.

## What it cannot establish

The fixture has no consented principals, team/project identity, production
authority, changed-system state, human satisfaction, or causal skill
improvement. It therefore cannot answer who in an enterprise has the same work,
which skills a user is missing, or whether a mined artifact improves the next
task. It is also not evidence that a tool retrieval model or embedding model is
better; those require running the evaluator under fixed model and budget arms.

## Frankengate adaptation

Add these fields when translating the fixture into our trace schema:

```text
trajectory_id, principal/team/project/system scope, exposure event,
candidate tool/artifact id, ordered dependency edges, authority decision,
parameter binding result, execution status, independent terminal outcome,
changed-environment id, and abstention/rejection reason
```

The next reproduction should compare static retrieval, LRAT-style exposure
supervision, and TOOLQP-style staged retrieval while holding the tool pool and
queries fixed. Every candidate acceptance must still pass governed replay.

Receipt: [`traject-bench-structural-audit-2026-08-09.json`](../results/traject-bench-structural-audit-2026-08-09.json)

## Claim boundary

This audit measures public benchmark structure only. It does not measure model
quality, agent intervention utility, enterprise user behavior, semantic alias
truth, or production-safe artifact reuse.
