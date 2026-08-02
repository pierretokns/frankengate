# Current Codex archive import and friction-screen baseline (2026-08-08)

## What was fixed

The current Codex archive format stores one rollout per
`archived_sessions/rollout-*.jsonl` file and places events under `payload`.
The older adapter grouped records by a message-level identifier and therefore
misreported the local archive as 1,328,071 sessions with zero user prompts.
That result is invalid and is not used.

`codex_archive_history_mining.py` treats each rollout file as one session and
handles current `user_message`, `agent_message`, `function_call`,
`function_call_output`, `custom_tool_call`, and `custom_tool_call_output` events.
It emits only per-session counters, hashes, tool-name counts, and timestamp
ranges; prompts, arguments, outputs, and paths are not written to the receipt.

## Local baseline

The local archive contained **622 rollout sessions**:

| Signal | Count |
|---|---:|
| User prompts / episode candidates | 47,122 |
| Function calls | 53,684 |
| Function-call outputs | 53,682 |
| Custom tool calls | 48,653 |
| Structured non-zero process outcomes | 2,060 |
| Sessions with a structured error | 181 |
| Repeated tool invocations | 16,349 |
| Adjacent rephrase pairs | 228 |
| Prompts with explicit friction markers | 10,662 episodes |
| Episodes with structured errors | 428 |
| Error→success episodes (marker-based) | 273 |
| Error→repair-follow-up prompt pairs | 33 |
| Error episodes with no success marker | 155 |

These are screening signals, not labels of user intent, satisfaction, or task
quality. In particular, the “success” counter is a textual marker in a tool
output, not an independent evaluation outcome. The archive is a valuable local
source for candidate friction/eval mining, but it still lacks stable
task-level gold outcomes and consent-scoped cross-user labels needed for the
enterprise causal replay gate.

## What this enables next

1. Select content-free candidate episodes by error, repair, repeated tool, and
   rephrase signals.
2. Re-read only authorized raw episodes locally to construct blinded eval cases;
   never treat the screening receipt as a semantic label.
3. Attach independent human or deterministic task outcomes before comparing
   artifact reuse, skill candidates, embeddings, or frontier adjudication.
4. Preserve the rollout file hash, principal/team/project scope, time, and
   deletion receipt in the authorized cohort manifest.

## Receipt and code

- External receipt: `/private/tmp/frankengate-codex-archive-history-2026-08-08-v2.json`
- [`codex_archive_history_mining.py`](../../codex_archive_history_mining.py)
- [`test_codex_archive_history_mining.py`](../../tests/test_codex_archive_history_mining.py)

