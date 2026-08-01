# DataClaw multi-harness corpus audit (2026-08-05)

We sampled 32 evenly spaced sessions from the pinned Hugging Face revision of
[`zhiyaowang/dataclaw-zhiyaowang`](https://huggingface.co/datasets/zhiyaowang/dataclaw-zhiyaowang/tree/f5157333cbc22489661122a9bc5347b137144900).
The corpus has 1,013 sessions across 77 projects and is MIT-licensed. It
contains Claude Code, Codex CLI, Cursor, Gemini, and OpenCode histories with
tool uses and, when available, tool outputs. The 7+ GB source file was queried
through the Hugging Face rows API; no raw content was downloaded into the
repository.

## Sample result

| measure | value |
|---|---:|
| total sessions in source | 1,013 |
| sampled sessions | 32 |
| distinct source categories in sample | 4 (hashed) |
| distinct model categories in sample | 14 (hashed) |
| distinct project categories in sample | 15 (hashed) |
| sessions with tool-output text | 11/32 |
| sessions with structured/raw tool output | 7/32 |
| sessions with an explicit branch | 17/32 |
| sessions with an explicit tool error | 5/32 |
| sessions with repeated tool-call shapes | 26/32 |
| distinct normalized content fingerprints | 3,332 |
| recurring successful artifact candidates (≥2 sessions) | 13 |
| recurring candidates spanning ≥2 project labels | 10 |
| fingerprints observed in both success and error calls | 4 |
| sessions with same-shape error→success transition | 4/32 |
| mean messages/session | 170.469 |
| mean tool uses/session | 124.531 |
| mean explicit error tools/session | 2.594 |

Across the sample there were 873 user messages and 4,582 assistant messages.
The dominant tool families were shell (2,427 calls), read/search (812), file
mutation (405), delegation (193), external retrieval (61), and other (87).
Tool statuses included 3,456 successes, 208 completed calls, and 76 explicit
errors.

## What this changes

This is materially better suited to artifact/friction mining than the earlier
flattened Peter DataClaw mirror: it has multiple harnesses, project/model
metadata, structured tool calls, and some tool outputs. It supports a new
multi-harness candidate-mining and recovery-analysis stratum.

The hash-only recurrence screen found 13 normalized call-input fingerprints
that occurred successfully in at least two sessions, including 10 spanning at
least two project labels. Four fingerprints appeared in both successful and
error calls, and four sessions contained an error followed by a later success
with the same normalized fingerprint. These are useful candidate and recovery
signals, but they are not proof that the command was correct, safe, optimal,
or transferable; normalization intentionally collapses paths and numeric
literals.

It still does **not** establish cross-user enterprise learning. The sample has
no independently verified task-success labels, organizational identity,
capability labels, or changed-system outcomes. Project and model fields are
metadata categories, not people or enterprise teams. Repeated call shapes are
candidate signals, not validated reusable skills.

The appropriate next experiment is therefore a content-bearing, consented
subset with independent task-boundary/outcome labels: compare deterministic
artifact candidates, identifier-aware retrieval, and frontier adjudication on
project/time/harness-held-out tasks, then replay accepted artifacts in a
changed environment. This corpus should not be used to auto-promote skills
from frequency alone.

Receipt: [`dataclaw-zhiyaowang-audit-2026-08-05.json`](../results/dataclaw-zhiyaowang-audit-2026-08-05.json).
