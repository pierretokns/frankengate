# DataClaw multi-harness corpus audit (2026-08-05)

We sampled 32 sessions in eight evenly spaced four-session windows from the pinned Hugging Face revision of
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
| distinct model categories in sample | 13 (hashed) |
| distinct project categories in sample | 16 (hashed) |
| sessions with tool-output text | 12/32 |
| sessions with structured/raw tool output | 5/32 |
| sessions with an explicit branch | 15/32 |
| sessions with an explicit tool error | 5/32 |
| sessions with repeated tool-call shapes | 25/32 |
| distinct normalized content fingerprints | 2,592 |
| recurring successful artifact candidates (≥2 sessions) | 9 |
| recurring candidates spanning ≥2 project labels | 2 |
| recurring candidates spanning ≥2 harness labels | 0 |
| recurring candidates spanning ≥2 model labels | 4 |
| fingerprints observed in both success and error calls | 2 |
| sessions with same-shape error→success transition | 2/32 |
| mean messages/session | 57.969 |
| mean tool uses/session | 120.438 |
| mean explicit error tools/session | 0.812 |

Across the sample there were 233 user messages and 1,622 assistant messages.
The dominant tool families were shell (2,301 calls), file mutation (1,117),
read/search (301), delegation (89), external retrieval (5), and other (41).
Tool statuses included 1,846 successes, 47 completed calls, and 23 explicit
errors.

## What this changes

This is materially better suited to artifact/friction mining than the earlier
flattened Peter DataClaw mirror: it has multiple harnesses, project/model
metadata, structured tool calls, and some tool outputs. It supports a new
multi-harness candidate-mining and recovery-analysis stratum.

The hash-only recurrence screen found 9 normalized call-input fingerprints that
occurred successfully in at least two sessions, including 2 spanning at least
two project labels and 4 spanning model labels. No recurring candidate crossed
two harness-source labels in this sample. Two fingerprints appeared in both
successful and error calls, and two sessions contained an error followed by a
later success with the same normalized fingerprint. These are useful
candidate and recovery signals, but they are not proof that the command was
correct, safe, optimal, or transferable; normalization intentionally collapses
paths and numeric literals.

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
