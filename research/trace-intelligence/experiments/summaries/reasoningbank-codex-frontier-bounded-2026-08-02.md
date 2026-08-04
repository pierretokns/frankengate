# ReasoningBank Codex frontier reproduction

The pinned upstream ReasoningBank runner was executed unchanged on LOCOMO,
with only its memory LLM client replaced by a Codex-subscription adapter after
the documented Azure provider was unavailable. Retrieval used local
`BAAI/bge-small-en-v1.5` embeddings (384 dimensions), and evaluation was frozen
so validation queries could not append memories.

Two train tasks produced two memory entries. On the same two held-out tasks as
the matched no-harness control:

| Arm | Mean LOCOMO score | Regressions |
| --- | ---: | ---: |
| No harness | 0.703 | — |
| ReasoningBank + Codex memory judge | 0.593 | 1 |

The delta was `-0.110`; one task tied and one regressed. This is a bounded
negative result under explicit provider substitutions, not a universal claim
that ReasoningBank cannot help. The arm is not eligible for Frankengate
promotion.

Raw trajectories and memory text remain outside the repository; the receipt
contains only hashes, task IDs, scalar scores, and claim boundaries.
