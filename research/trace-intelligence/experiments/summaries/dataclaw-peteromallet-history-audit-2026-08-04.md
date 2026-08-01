# Real-user DataClaw history audit (2026-08-04)

## Corpus

The licensed MIT `peteromallet/dataclaw-peteromallet` export contains 549
Claude Code sessions across 14 projects, 169,168 messages, and approximately
80,409 tool uses. It includes project/model/session metadata and tool-call
inputs, but intentionally omits tool outputs. This is a materially better
source for longitudinal user research than synthetic traces, but it is still a
single-user corpus and cannot establish cross-user transfer.

## Content-free interaction signals

- 400/549 sessions (72.9%) contain at least one broad friction-language signal;
  this is a **candidate detector**, not a failure rate. The detector includes
  words such as “still”, “actually”, “again”, “wrong”, and “error”, so it must
  be calibrated against adjudicated outcomes.
- 1,498 adjacent re-prompt/correction pairs were detected by lexical overlap or
  correction markers. These are useful review candidates for deriving intent,
  but they do not prove that the preceding answer was wrong.
- 3,243 non-trivial tool-call forms recur across sessions; 590 recur across
  different project labels. These are candidate reusable commands/actions, not
  known-good artifacts.
- The model mix is mostly Opus (526/549 sessions), with 16 Sonnet and 6 Haiku
  sessions, which makes model comparisons confounded by user/project/time.

## Claim boundary

The export supports a real-user longitudinal friction and candidate-artifact
study. It does **not** support automatic skill promotion, causal improvement,
success labels, or cross-user collaboration recommendations: tool outputs,
independent verification, task outcomes, and a second principal are absent.

The content-free receipt is
`experiments/results/dataclaw-peteromallet-history-audit-2026-08-04.json`; its
verifier passes. Prompt and tool text are processed locally and are not emitted
into the receipt.

## Research consequence

This corpus is suitable for the next controlled stage: sample repeated
tool/action candidates and friction pairs, reconstruct the task boundary, then
replay them with independent success/security checks and no-skill/placebo
controls. A repeated command should become a governed artifact only after that
validation, not merely because it appears often in history.
