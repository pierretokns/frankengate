# Native-tool terminal protocol pilot

This content-free experiment tests whether the pinned local model can complete
a native-tool loop under three arm-independent tool-availability policies. It
contains no Defog, BIRD, selection-stage, hidden-stage, gold-SQL, database, or
enterprise trace content. It is not an SQL-quality experiment.

## Frozen design

Six synthetic fixtures—three requiring submission of a successful attempt and
three requiring abstention after synthetic policy denials—were run under a
position-balanced, paired schedule:

1. `always_all_tools`: expose schema, SQL execution, submission, and abstention
   on every turn;
2. `remaining_budget_annotations`: expose the same tools while annotating their
   descriptions with remaining budgets; and
3. `terminal_only_after_sql_budget`: after two SQL attempts, expose only
   `submit_sql` and `abstain`.

The manifest was frozen before the live run. Complete requests, responses,
offered schemas, native calls, parsed arguments, and tool results remain in 18
external JSONL audit files under `/private/tmp`; only content-minimized receipts
and hashes are committed.

## Result

| Variant | Episodes | Expected terminal action | Terminal failures | Over-budget SQL calls | Unavailable calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Always all tools | 6 | 6/6 | 0 | 0 | 0 |
| Remaining-budget annotations | 6 | 6/6 | 0 | 0 | 0 |
| Terminal-only after SQL budget | 6 | 6/6 | 0 | 0 | 0 |

The run made 72 model calls and 72 native tool calls, used 57,684 prompt and
2,322 completion tokens, and recorded 132,751.758 ms of model latency. All 18
raw audit hashes were distinct. The aggregate file SHA-256 is
`f2b33149b8c16f0209516433cdbe55d4a7d5b61315916425a03abfd736817c59`;
its self-reported canonical aggregate hash is
`09312ccd597e8cb9bd41e289e092561e94f6af9911ecbe9dd2b4039ee38d6f4d`.

The exact executable inputs are bound by these receipts:

| Input | SHA-256 |
| --- | --- |
| Protocol runner | `a7f0e40e8587ca5213017ef3260f587c2547b80a4258532e79d9c3005853cbb8` |
| Frozen fixture manifest | `e9657dc7a3421a916e261527311e07ef5afc37497a6ba6f646bbb9cd6c8b25b4` |
| Model/runtime manifest | `e136e8541ee96995573e0d1eb7fdec2ebc06b2bde53c97e3686b0e80228eda6b` |
| Imported native-tool contract | `5abfe01adb56de7679faa37d204b0ca2c7f8ff8fa1205a314281c21f09050fed` |

## Decision

Terminal-only tool switching is technically compatible with the pinned
Qwen3.5/MLX runtime and preserves the intended submit/abstain behavior in this
fixture. It is therefore admissible for a harder independent confirmation and,
after capability isolation is implemented, a newly versioned four-task P0.

The pilot does **not** show that terminal-only availability caused an
improvement: the two controls also achieved 100% compliance. The fixture's
explicit instruction was easier than the original Defog episodes. The original
P0 remains failed, P1 remains blocked, and hidden-stage results remain sealed.

## Reproduce

Launch the exact local model snapshot and cache-disabled runtime specified in
`configs/models/qwen3.5-9b-optiq-4bit-mlx.json`, then run:

```sh
python3 research/trace-intelligence/native_tool_protocol_compliance.py \
  --endpoint http://127.0.0.1:18080 \
  --model default_model \
  --raw-audit-dir /private/tmp/frankengate-native-tool-protocol-pilot-20260730 \
  --output research/trace-intelligence/experiments/results/native-tool-protocol-compliance-pilot-2026-07-30.json
```

The runner refuses to overwrite an aggregate or append to an existing episode
audit and rejects raw-audit paths inside the repository.
