# Strict tool-artifact recurrence and recovery in Claude histories

## Question

Do real coding-agent histories contain enough repeated tool calls and outcomes
to seed a governed artifact or skill library?

## Protocol

The scan covered 442 local `.claude/projects` JSONL sessions from the public
Brainflow history export. Every assistant `tool_use` was paired to its
`tool_result` by ID. A strict artifact identity is the tool name plus a
normalized input: paths, UUIDs, and multi-digit numbers are canonicalized, but
the remaining input structure and text remain part of the identity. An
explicit `is_error` flag supplies the observed result status. Recurrence is
counted only across distinct sessions; cross-project recurrence requires two
project-directory hashes. No tool name, argument, path, result, or session
identifier is written to the receipt.

## Results

| Measure | Result |
|---|---:|
| Tool uses | 70,969 |
| Paired tool results | 70,949 |
| Explicit successes / errors | 64,367 / 6,582 |
| Distinct strict normalized artifact identities | 51,424 |
| Successful artifacts recurring across sessions | 2,012 |
| Successful artifacts recurring across projects | 1,105 |
| Recurring artifacts with mixed success/error outcomes | 431 |
| Artifacts recurring as failures | 137 |
| Same-session error→success recoveries | 3,866 |

Of the 2,012 successful recurring artifacts, 1,105 crossed a project boundary
(54.92%). This is a substantial candidate pool for review, but the strict
identity and explicit tool status do not establish that the operation was
semantically correct, safe, optimal, or desired by the user.

## Interpretation

This is the strongest available public-history evidence for a **candidate
artifact lane**:

```text
strict tool/input recurrence + observed status
  -> scope/authority and context checks
  -> error/recovery and hard-negative review
  -> clean-environment replay
  -> changed-system replay
  -> versioned skill/tool artifact
```

The 3,866 recovery transitions are particularly useful for mining repair/eval
candidates. Mixed-outcome identities (431) are an immediate warning against
promoting by frequency alone. Cross-project recurrence is candidate recall,
not proof of cross-user transfer; the prior strict DataClaw transfer study
found zero shared strict identities between two users.

## Claim boundary

The export lacks independent terminal task outcomes, tool safety contracts,
semantic intent labels, and changed-environment replay. Therefore this study
does not establish artifact correctness, skill improvement, or user benefit.
It establishes that the raw trace format contains the structural evidence
needed to build a governed review/replay queue.

## Receipts

- [content-free result](../results/claude-history-tool-artifact-miner-2026-08-09.json)
- [independent verification](../results/claude-history-tool-artifact-miner-verification-2026-08-09.json)
- [`claude_history_tool_artifact_miner.py`](../../claude_history_tool_artifact_miner.py)
