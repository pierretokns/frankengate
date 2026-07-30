# MLX-LM native-tool runtime audit

This audit freezes the local runtime used for the first governed Defog
mechanics experiment. It is a runtime qualification, not a model-quality
result.

## Decision

Use
[`mlx-community/Qwen3.5-9B-OptiQ-4bit`](https://huggingface.co/mlx-community/Qwen3.5-9B-OptiQ-4bit)
at revision `319aed167e31e0bf81ddba0c23f8d218a15be612` for the mechanics
smoke and first intervention-sensitivity screen. The local snapshot is
7,120,886,349 bytes and has identity receipt
`7174d7cb2996ec7e22831448c055d3339640f7a43d81d606a875c8728dc0a638`.
It is the smallest locally resident model whose tokenizer explicitly selects
MLX-LM's `qwen3_coder` native-tool parser.

The final pilot runs sequentially, non-streaming, on loopback with temperature zero,
top-p one, top-k zero, min-p zero, a paired task seed, thinking disabled, and
prompt/decode concurrency one. Prompt-cache size is zero so no KV state is
retained across scientific episodes. It must not be described as a
frontier-model or production-serving result.

The request body must use `model: "default_model"`. A live audit showed that
sending the Hugging Face repository ID causes MLX-LM to resolve the repository's
mutable `main` revision dynamically, even when the server was launched from an
immutable local snapshot. That contaminated process was stopped and none of its
outputs are admitted. Scientific identity comes from the recorded local
snapshot revision and digest, not from the request model string or system
fingerprint.

## Runtime pin

| Component | Version or receipt |
| --- | --- |
| MLX-LM | v0.31.3, `ed1fca4cef15a824c5f1702c80f70b4cffc8e4dd` |
| MLX | 0.31.2 |
| Transformers | 5.8.1 |
| Hugging Face Hub | 1.15.0 |
| `mlx_lm/server.py` | `cdfcb4ac848636f9927851a0ec7a951584526530cb7832ba58049e4a9144db8b` |
| `mlx_lm/tokenizer_utils.py` | `25784bb03c922d0d7832ce6c66a6cd4eb3a4820b6c5a8e583dedb63a018fb56a` |
| `mlx_lm/tool_parsers/qwen3_coder.py` | `32de6d9f7472a1f00a2acfaac13e0e0864cfc19adebbff688ac5004b8ecc25` |

The complete model/runtime pin is
`configs/models/qwen3.5-9b-optiq-4bit-mlx.json`.

## Verified behavior

A loopback smoke request produced a native `tool_calls` response for an
`add(a, b)` function. The response used the expected OpenAI-compatible message
shape and the runtime fingerprint reported MLX-LM 0.31.3 and MLX 0.31.2.

The runtime accepts `messages`, `tools`, decoding controls, seed, and chat
template arguments. It does **not** enforce request-side `tool_choice`,
`parallel_tool_calls`, `response_format`, authentication, or rejection of
unknown JSON members. Frankengate's experiment runner must therefore validate
native tool calls itself and must not claim that the server forced tool use.

## Failure boundaries

- Bind the server only to `127.0.0.1`; it has no request authentication and is
  not a production server.
- A parser failure can drop a malformed or truncated tool call while the finish
  reason remains `tool_calls`. This is a protocol failure, not an abstention.
- Completion and tool-call IDs are UUIDs. Normalize IDs for determinism without
  removing function names or arguments.
- The runtime fingerprint does not identify the model snapshot. Every result
  must carry the immutable model revision and snapshot receipt.
- Never send the repository ID as the request's `model`; use the server's
  `default_model` alias to prevent mutable remote resolution.
- Per-request seeding disables batching. This is desirable for paired science
  but cannot support a serving-throughput claim.
- Shared prompt/KV-cache isolation is not established for concurrent scientific
  episodes. Keep concurrency at one and use a fresh conversation per task-arm.
- Bound turns and context growth: prior MLX-LM reports show hard Metal
  out-of-memory exits rather than a recoverable HTTP response.

## Sources

Primary sources:

- [MLX-LM v0.31.3](https://github.com/ml-explore/mlx-lm/releases/tag/v0.31.3)
- [Parallel tool-call fix](https://github.com/ml-explore/mlx-lm/pull/1170)
- [Concurrent KV-cache isolation report](https://github.com/ml-explore/mlx-lm/issues/965)
- [Metal OOM server abort](https://github.com/ml-explore/mlx-lm/issues/854)
- [Local snapshot-download failure loop](https://github.com/ml-explore/mlx-lm/issues/1208)
- [Qwen3.6 MTP prefix-cache truncation](https://github.com/ml-explore/mlx-lm/issues/1292)

Installed source was audited at the hashes above. The model repository's
`config.json`, tokenizer config, chat template, generation config, weight
index, and OptiQ metadata receipts are recorded in the model manifest.
