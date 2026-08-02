# Claude command-artifact normalization audit

## Question

Does parameterized command identity preserve the useful same-scope success
prior, or does redacting paths/numbers/UUIDs merge unrelated commands and make
artifact reuse unsafe?

## Protocol

The audit parses the locally cached Wisp Claude Code session tree. It pairs
`Bash` tool uses with their native `tool_result` records, labels only the
explicit `is_error` outcome, and compares exact command hashes with the
parameterized normalization used by the Codex command audit. The receipt keeps
only aggregate counts and hashes; no command, path, output, or session ID is
committed, and no command is executed.

## Decision gate

Parameterized identity is acceptable as a candidate retrieval key only if it
does not materially inflate mixed outcomes or erase scope boundaries. Even a
good operational prior is not a semantic artifact: intent labels, authority,
side-effect contracts, and changed-environment replay remain required before
automatic reuse.

## Result

The cohort contained 1,352 paired Bash outcomes across 214 JSONL files, with a
95.34% overall success rate. Exact command identity produced 1,301 artifact
buckets, 23 same-scope repeats, and no mixed-outcome buckets. Parameterized
identity reduced this to 1,161 buckets, created **29** buckets containing
multiple exact commands and **140** additional exact-command collisions, and
created **3** mixed-outcome buckets. Same-scope repeats were all successful in
both representations, but the cohort is too easy to estimate failure lift.

The safe design implication is structural: retain exact invocation identity,
scope, and parameter bindings separately. A normalized key may expand candidate
recall, but it must not authorize replay by itself.

## Claim boundary

This is a cross-harness mechanics and normalization audit, not a user-intent,
semantic-equivalence, or productivity study.

Receipts:

- [content-free result](../results/claude-command-artifact-normalization-2026-08-09.json)
- [independent verification](../results/claude-command-artifact-normalization-verification-2026-08-09.json)
- [`claude_command_artifact_normalization_audit.py`](../../claude_command_artifact_normalization_audit.py)
