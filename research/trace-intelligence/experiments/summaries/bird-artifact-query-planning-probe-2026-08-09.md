# Outcome-backed SQL artifact query-planning probe (2026-08-09)

This applies the portable mechanism from ToolQP—generate subtask-oriented
retrieval queries—to the harder BIRD trace-artifact setting. It is not a
ToolQP training reproduction.

The cohort contains 76 independently validated SQL artifacts mined from
recorded BIRD traces. We selected 16 targets round-robin across 11 database
families. For each target, the planner saw the natural-language question and a
lexical shortlist of other same-family artifacts. It did not see the target
SQL, execution results, or result-match labels. It generated three queries;
the union was ranked, then every top candidate was executed against the target
database.

## Result

| Arm | Targets | Result match @1 | @5 | @10 |
|---|---:|---:|---:|---:|
| Lexical baseline | 16 | 0 | 0 | 0 |
| Query-planning union | 16 | 0 | 0 | 0 |

The planner did not recover a reusable validated SQL artifact in this slice.
This is consistent with the larger prior cascade: among all 76 validated
artifacts, lexical, identifier, dense, and hybrid retrieval produced only
`0/76` result matches at top-1, `1/76` at top-5, and `2/76` at top-10.

## Interpretation

This is not evidence that query planning is useless. It isolates a harder
precondition: the recorded BIRD artifact pool contains almost no natural
repeated SQL templates or semantically equivalent procedures. Query expansion
can improve retrieval coverage only when a compatible artifact exists in the
candidate pool. It cannot manufacture a missing procedure.

For Frankengate, ToolQP-style planning belongs after a validated artifact
library has repeated intents/subplans. The next decisive cohort needs reviewed
same-intent SQL/tool artifacts, parameterized templates, and independently
validated changed-system outcomes. Until then, the correct fallback is
frontier regeneration plus execution validation—not automatic reuse.

Receipts:

- [probe result](../results/bird-artifact-query-planning-probe-2026-08-09.json)
- [independent verification](../results/bird-artifact-query-planning-probe-verification-2026-08-09.json)
- [runner](../../bird_artifact_query_planning_probe.py)
- [verifier](../../verify_bird_artifact_query_planning_probe.py)

Raw prompts, SQL, and model outputs remain external; the committed receipt
contains only hashes, aggregate outcomes, and task identifiers.
